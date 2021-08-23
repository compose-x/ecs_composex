#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to handle elbv2.
"""

import re
import warnings
from copy import deepcopy
from json import dumps

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import (
    AWS_NO_VALUE,
    AWS_STACK_NAME,
    FindInMap,
    GetAtt,
    Ref,
    Select,
    Sub,
    Tags,
)
from troposphere.cognito import UserPoolClient
from troposphere.ec2 import EIP, SecurityGroup
from troposphere.elasticloadbalancingv2 import (
    Action,
    AuthenticateCognitoConfig,
    AuthenticateOidcConfig,
    Certificate,
    Condition,
    FixedResponseConfig,
    ForwardConfig,
    HostHeaderConfig,
    Listener,
    ListenerCertificate,
    ListenerRule,
    LoadBalancer,
    LoadBalancerAttributes,
    PathPatternConfig,
    RedirectConfig,
    SubnetMapping,
    TargetGroupTuple,
)

from ecs_composex.acm.acm_params import MOD_KEY as ACM_MOD_KEY
from ecs_composex.acm.acm_params import RES_KEY as ACM_KEY
from ecs_composex.cognito_userpool.cognito_params import MAPPINGS_KEY as COGNITO_MAP
from ecs_composex.cognito_userpool.cognito_params import RES_KEY as COGNITO_KEY
from ecs_composex.cognito_userpool.cognito_params import (
    USERPOOL_ARN,
    USERPOOL_DOMAIN,
    USERPOOL_ID,
)
from ecs_composex.common import LOG, NONALPHANUM, add_parameters, build_template
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, Parameter
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.elbv2.elbv2_params import (
    LB_DNS_NAME,
    LB_DNS_ZONE_ID,
    LB_SG_ID,
    MOD_KEY,
    RES_KEY,
)
from ecs_composex.ingress_settings import Ingress, set_service_ports
from ecs_composex.resources_import import import_record_properties
from ecs_composex.vpc.vpc_params import APP_SUBNETS, PUBLIC_SUBNETS, VPC_ID


def handle_cross_zone(value):
    return LoadBalancerAttributes(
        Key="load_balancing.cross_zone.enabled", Value=str(value).lower()
    )


def handle_http2(value):
    return LoadBalancerAttributes(Key="routing.http2.enabled", Value=str(value).lower())


def handle_drop_invalid_headers(value):
    return LoadBalancerAttributes(
        Key="routing.http.drop_invalid_header_fields.enabled",
        Value=str(value).lower(),
    )


def handle_desync_mitigation_mode(value):
    if value not in ["defensive", "strictest", "monitor"]:
        raise ValueError(
            "desync_mitigation_mode must be one of",
            ["defensive", "strictest", "monitor"],
        )
    return LoadBalancerAttributes(
        Key="routing.http.desync_mitigation_mode", Value=str(value).lower()
    )


def handle_timeout_seconds(timeout_seconds):
    if 1 < int(timeout_seconds) < 4000:
        return LoadBalancerAttributes(
            Key="idle_timeout.timeout_seconds",
            Value=str(timeout_seconds).lower(),
        )
    else:
        raise ValueError(
            "idle_timeout.timeout_seconds must be set between 1 and 4000 seconds. Got",
            timeout_seconds,
        )


def validate_listeners_duplicates(name, ports):
    if len(ports) != len(set(ports)):
        s = set()
        raise ValueError(
            f"{name} - More than one listener with port {set(x for x in ports if x in s or s.add(x))}"
        )


def add_listener_certificate_via_arn(listener, certificates_arn):
    """

    :param ecs_composex.elbv2.elbv2_stack.ComposeListener listener:
    :param list certificates_arn: list of str or other defined ARN
    :return:
    """
    ListenerCertificate(
        f"AcmCert{listener.title}",
        template=listener.template,
        Certificates=[Certificate(CertificateArn=arn) for arn in certificates_arn],
        ListenerArn=Ref(listener),
    )


def http_to_https_default(default_of_all=False):
    return Action(
        RedirectConfig=RedirectConfig(
            Protocol="HTTPS",
            Port="443",
            Host="#{host}",
            Path="/#{path}",
            Query="#{query}",
            StatusCode=r"HTTP_301",
        ),
        Type="redirect",
        Order=Ref(AWS_NO_VALUE) if not default_of_all else 50000,
    )


def tea_pot(default_of_all=False):
    return Action(
        FixedResponseConfig=FixedResponseConfig(
            ContentType="application/json",
            MessageBody=dumps({"Info": "Be our guest"}),
            StatusCode="HTTP_418",
        ),
        Type="fixed-response",
        Order=Ref(AWS_NO_VALUE) if not default_of_all else 50000,
    )


def handle_predefined_redirects(listener, action_name):
    """
    Function to handle predefined redirects
    :return:
    """
    predefined_redirects = [
        ("HTTP_TO_HTTPS", http_to_https_default),
    ]
    if action_name not in [r[0] for r in predefined_redirects]:
        raise ValueError(
            f"Redirect {action_name} is not a valid pre-defined setting. Valid values",
            [r[0] for r in predefined_redirects],
        )
    for redirect in predefined_redirects:
        if action_name == redirect[0]:
            action = redirect[1]()
            listener.DefaultActions.insert(0, action)


def handle_default_actions(listener):
    action_sources = [("Redirect", handle_predefined_redirects)]
    for action_def in listener.default_actions:
        action_source = list(action_def.keys())[0]
        source_value = action_def[action_source]
        if action_source not in [a[0] for a in action_sources]:
            raise KeyError(
                f"Action {action_source} is not supported. Supported actions",
                [a[0] for a in action_sources],
            )
        for action in action_sources:
            if action_source == action[0]:
                action[1](listener, source_value)


def handle_string_condition_format(access_string):
    """
    Function to parse and understand what type of condition that is.
    Supported :
    * path based
    * domain name

    :param access_string:
    :return:
    """
    domain_path_re = re.compile(
        r"^((?=.{1,255}$)(?!-)[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63})*\.?(?<!-))(?::[0-9]{1,5})?(/[\S]+$)"
    )
    domain_re = re.compile(
        r"^(?=.{1,255}$)(?!-)[A-Za-z0-9\-]{1,63}(\.[A-Za-z0-9\-]{1,63})*\.?(?<!-)$"
    )
    path_re = re.compile(r"(?:.*)^[/][\S]+$")
    if (
        domain_path_re.match(access_string)
        and len(domain_path_re.match(access_string).groups()) == 2
    ):
        return [
            Condition(
                Field="host-header",
                HostHeaderConfig=HostHeaderConfig(
                    Values=[domain_path_re.match(access_string).groups()[0]],
                ),
            ),
            Condition(
                Field="path-pattern",
                PathPatternConfig=PathPatternConfig(
                    Values=[domain_path_re.match(access_string).groups()[1]]
                ),
            ),
        ]
    elif domain_re.match(access_string):
        return [
            Condition(
                Field="host-header",
                HostHeaderConfig=HostHeaderConfig(
                    HttpHeaderName="Host", Values=[access_string]
                ),
            )
        ]
    elif path_re.match(access_string):
        return [
            Condition(
                Field="path-pattern",
                PathPatternConfig=PathPatternConfig(Values=[access_string]),
            )
        ]
    else:
        raise ValueError(f"Could not understand what the access is for {access_string}")


def define_target_conditions(definition):
    """
    Function to create the conditions for forward to target
    :param definition:
    :return: list of conditions
    :rtype: list
    """
    conditions = []
    if isinstance(definition["access"], str):
        return handle_string_condition_format(definition["access"])
    return conditions


def define_actions(listener, target_def):
    """
    Function to identify the Target definition and create the resulting rule appropriately.

    :param dict target_def:
    :param ecs_composex.elbv2.elbv2_stack.ComposeListener listener:
    :return: The action to add or action list for default target
    """
    if not keyisset("target_arn", target_def):
        raise KeyError("No target ARN defined in the target definition")
    auth_action = None
    actions = []
    if keyisset("AuthenticateCognitoConfig", target_def):
        auth_action_type = "authenticate-cognito"
        props = import_record_properties(
            target_def["AuthenticateCognitoConfig"], AuthenticateCognitoConfig
        )
        auth_rule = AuthenticateCognitoConfig(**props)
        auth_action = Action(
            Type=auth_action_type, AuthenticateCognitoConfig=auth_rule, Order=1
        )
    elif keyisset("AuthenticateOidcConfig", target_def):
        auth_action_type = "authenticate-oidc"
        props = import_record_properties(
            target_def["AuthenticateOidcConfig"], AuthenticateOidcConfig
        )
        auth_rule = AuthenticateOidcConfig(**props)
        auth_action = Action(
            Type=auth_action_type, AuthenticateOidcConfig=auth_rule, Order=1
        )
    if auth_action:
        if hasattr(listener, "Certificates") and not listener.Certificates:
            raise AttributeError(
                "In order to use authenticate via OIDC or AWS Cognito,"
                " your listener must be using HTTPs and have SSL Certificates defined."
            )
        if not listener.Protocol == "HTTPS":
            raise AttributeError(
                "In order to use authenticate via OIDC or AWS Cognito,",
                "Your listener protocol MUST be HTTPS. Got",
                listener.Protocol,
            )
        actions.append(auth_action)
        actions.append(
            Action(
                Type="forward",
                ForwardConfig=ForwardConfig(
                    TargetGroups=[
                        TargetGroupTuple(TargetGroupArn=target_def["target_arn"])
                    ]
                ),
                Order=2,
            )
        )
    else:
        actions.append(
            Action(
                Type="forward",
                ForwardConfig=ForwardConfig(
                    TargetGroups=[
                        TargetGroupTuple(TargetGroupArn=target_def["target_arn"])
                    ]
                ),
                Order=1,
            )
        )
    return actions


def define_listener_rules_actions(listener, left_services):
    """
    Function to identify the Target definition and create the resulting rule appropriately.

    :param dict service_def:
    :param listener:
    :param list left_services:
    :return: The action to add or action list for default target
    """
    rules = []
    for count, service_def in enumerate(left_services):
        rule = ListenerRule(
            f"{listener.title}{NONALPHANUM.sub('', service_def['name'])}Rule",
            ListenerArn=Ref(listener),
            Actions=define_actions(listener, service_def),
            Priority=(count + 1),
            Conditions=define_target_conditions(service_def),
        )
        rules.append(rule)
    return rules


def handle_non_default_services(listener, services_def):
    """
    Function to handle define the listener rule and identify
    :param listener:
    :param services_def:
    :return:
    """
    default_target = None
    left_services = deepcopy(services_def)
    for count, service_def in enumerate(services_def):
        if isinstance(service_def["access"], str) and service_def["access"] == "/":
            default_target = service_def
            left_services.pop(count)
            break
    if not default_target:
        LOG.warning("No service path matches /. Defaulting to return TeaPot")
        listener.DefaultActions.append(tea_pot(True))
    elif default_target:
        listener.DefaultActions += define_actions(listener, default_target)
    rules = define_listener_rules_actions(listener, left_services)
    return rules


def validate_new_or_lookup_cert_matches(src_name, new_acm_certs, lookup_acm_certs):
    if src_name not in [
        new_cert.name for new_cert in new_acm_certs
    ] and src_name not in [new_cert.name for new_cert in lookup_acm_certs]:
        raise ValueError(
            "No new or looked up ACM certificate found.",
            src_name,
            "Expected one of ",
            [new_cert.name for new_cert in new_acm_certs],
            [new_cert.name for new_cert in lookup_acm_certs],
        )


def add_extra_certificate(listener, cert_arn):
    """
    Function to add Certificates to listener

    :param troposphere.elasticloadbalancingv2.Listener listener:
    :param cert_arn:
    :return:
    """
    if hasattr(listener, "Certificates"):
        certs = getattr(listener, "Certificates")
        certs.append(Certificate(CertificateArn=cert_arn))
    else:
        setattr(listener, "Certificates", [Certificate(CertificateArn=cert_arn)])


def rectify_listener_protocol(listener):
    """
    Function to rectify the listener type when adding cert

    :param troposphere.elasticloadbalancingv2.Listener listener:
    :raises: ValueError if trying to set TLS for UDP
    """
    alb_protocols = ["HTTP", "HTTPS"]
    nlb_protocols = ["TCP", "UDP", "TCP_UDP", "TLS"]
    if listener.Protocol in alb_protocols and listener.Protocol == "HTTP":
        LOG.warning(
            "Listener protocol is HTTP but certificate defined. Changing to HTTPS"
        )
        listener.Protocol = "HTTPS"
    elif listener.Protocol in nlb_protocols and listener.Protocol == "TCP":
        LOG.warning("Listener protocol is TCP but certificate defined. Changing to TLS")
        listener.Protocol = "TLS"
    elif listener.Protocol in nlb_protocols and (
        listener.Protocol == "UDP" or listener.Protocol == "TCP_UDP"
    ):
        raise ValueError("NLB configured with certificates require TLS.")


def import_new_acm_certs(listener, src_name, settings, listener_stack):
    """
    Function to Import an ACM Certificate defined in x-acm

    :param listener:
    :param src_name:
    :param settings:
    :param listener_stack:
    :return:
    """
    if not keyisset(ACM_KEY, settings.compose_content):
        raise LookupError(f"There is no {ACM_KEY} defined in your docker-compose files")
    new_acm_certs = [
        settings.compose_content[ACM_KEY][name]
        for name in settings.compose_content[ACM_KEY]
        if settings.compose_content[ACM_KEY][name].cfn_resource
    ]
    lookup_acm_certs = [
        settings.compose_content[ACM_KEY][name]
        for name in settings.compose_content[ACM_KEY]
        if settings.compose_content[ACM_KEY][name].lookup
    ]
    the_cert = None
    for cert in new_acm_certs:
        if cert.name == src_name:
            the_cert = cert
    if not the_cert:
        for cert in lookup_acm_certs:
            if cert.name == src_name:
                the_cert = cert
                break
    cert_param = Parameter(f"{the_cert.logical_name}Arn", Type="String")
    add_parameters(listener_stack.stack_template, [cert_param])
    if the_cert.cfn_resource and not the_cert.lookup:
        listener_stack.Parameters.update({cert_param.title: Ref(the_cert.cfn_resource)})
    elif the_cert.lookup and not the_cert.cfn_resource:
        listener_stack.Parameters.update(
            {
                cert_param.title: FindInMap(
                    ACM_MOD_KEY, the_cert.logical_name, the_cert.logical_name
                )
            }
        )
    add_extra_certificate(listener, Ref(cert_param))
    rectify_listener_protocol(listener)


def handle_import_cognito_pool(the_pool, listener_stack, settings):
    """
    Function to map AWS Cognito Pool to attributes
    :param the_pool:
    :param listener_stack:
    :param settings:
    :return:
    """
    if the_pool.cfn_resource and not the_pool.mappings:
        pool_id_param = Parameter(
            f"{the_pool.logical_name}{USERPOOL_ID.title}", Type="String"
        )
        pool_arn = Parameter(
            f"{the_pool.logical_name}{USERPOOL_ARN.title}", Type="String"
        )
        add_parameters(listener_stack.stack_template, [pool_id_param, pool_arn])
        listener_stack.Parameters.update(
            {
                pool_id_param.title: Ref(the_pool.cfn_resource),
                pool_arn.title: Ref(pool_arn),
            }
        )
        return Ref(pool_id_param), Ref(pool_arn)
    elif the_pool.mappings and not the_pool.cfn_resource:
        if (
            keyisset(COGNITO_KEY, settings.mappings)
            and COGNITO_MAP not in listener_stack.stack_template.mappings
        ):
            listener_stack.stack_template.add_mapping(
                COGNITO_MAP, settings.mappings[COGNITO_KEY]
            )
        return (
            FindInMap(COGNITO_MAP, the_pool.logical_name, USERPOOL_ID.title),
            FindInMap(COGNITO_MAP, the_pool.logical_name, USERPOOL_ARN.title),
            FindInMap(COGNITO_MAP, the_pool.logical_name, USERPOOL_DOMAIN.title),
        )


def import_cognito_pool(src_name, settings, listener_stack):
    """
    Function to Import an Cognito Pool defined in x-cognito_pool

    :param src_name:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param listener_stack:
    :return:
    """
    if not keyisset(COGNITO_KEY, settings.compose_content):
        raise LookupError(
            f"There is no {COGNITO_KEY} defined in your docker-compose files"
        )
    pool_names = [pool.name for pool in settings.compose_content[COGNITO_KEY].values()]
    if src_name not in pool_names:
        raise KeyError(f"{COGNITO_KEY} - pool {src_name} not found", pool_names)
    for pool in settings.compose_content[COGNITO_KEY].values():
        if src_name == pool.name:
            return handle_import_cognito_pool(pool, listener_stack, settings)
    raise LookupError("Failed to identify the cognito userpool to use", src_name)


def add_acm_certs_arn(listener, src_value, settings, listener_stack):
    """
    Function to add Certificate to Listener with input from manual ARN entry
    :param listener:
    :param str src_value:
    :param settings:
    :param listener_stack:
    :return:
    """
    cert_arn_re = re.compile(
        r"((?:^arn:aws(?:-[a-z]+)?:acm:[\S]+:[0-9]+:certificate/)"
        r"([a-z0-9]{8}(?:-[a-z0-9]{4}){3}-[a-z0-9]{12})$)"
    )
    if not cert_arn_re.match(src_value):
        raise ValueError(
            "The CertificateArn is not valid. Got",
            src_value,
            "Expected",
            cert_arn_re.pattern,
        )
    LOG.info("Adding new cert from defined ARN")
    add_extra_certificate(listener, src_value)
    rectify_listener_protocol(listener)


def map_service_target(lb, name, l_service_def):
    """
    Function to iterate over targets to map the service and its defined TargetGroup ARN

    :param ecs_composex.elbv2.elbv2_stack.Elbv2 lb:
    :param str name:
    :param dict l_service_def:
    :return:
    """
    for target in lb.families_targets:
        t_family = target[1].name
        t_service = target[0].name
        target_name = f"{t_family}:{t_service}"
        if target_name == name:
            for service in lb.services:
                if service["name"] == target_name:
                    l_service_def["target_arn"] = service["target_arn"]
                    break
            break


class ComposeListener(Listener):
    attributes = [
        "Condition",
        "CreationPolicy",
        "DeletionPolicy",
        "DependsOn",
        "Metadata",
        "UpdatePolicy",
        "UpdateReplacePolicy",
    ]

    targets_keys = "Targets"

    def __init__(self, lb, definition):
        """
        Method to init listener.

        :param ecs_composex.elbv2.elbv2_stack.Elbv2 lb:
        :param dict definition:
        """
        self.definition = deepcopy(definition)
        straight_import_keys = ["Port", "Protocol", "SslPolicy", "AlpnPolicy"]
        listener_kwargs = dict(
            (x, self.definition[x])
            for x in straight_import_keys
            if x in self.definition
        )
        listener_kwargs.update(
            dict(
                (x, self.definition[x]) for x in self.attributes if x in self.definition
            )
        )
        self.services = (
            self.definition[self.targets_keys]
            if keyisset(self.targets_keys, self.definition)
            and isinstance(self.definition[self.targets_keys], list)
            else []
        )
        self.default_actions = (
            self.definition["DefaultActions"]
            if keyisset("DefaultActions", self.definition)
            else []
        )
        listener_kwargs.update({"LoadBalancerArn": Ref(lb.lb)})
        self.name = f"{lb.logical_name}{listener_kwargs['Port']}"
        super().__init__(self.name, **listener_kwargs)
        self.DefaultActions = []

    def define_default_actions(self, template):
        """
        If DefaultTarget is set it will set it if not a service, otherwise at the service level.
        If not defined, and there is more than one service, it will fail.
        If not defined and there is only one service defined, it will skip
        """
        if not self.default_actions and not self.services:
            raise ValueError(
                f"There are no actions defined or services for listener {self.title}."
            )
        if self.default_actions:
            handle_default_actions(self)
        elif not self.default_actions and self.services and len(self.services) == 1:
            LOG.info(
                f"{self.title} has no defined DefaultActions and only 1 service. Default all to service."
            )
            self.DefaultActions = define_actions(self, self.services[0])
        elif not self.default_actions and self.services and len(self.services) > 1:
            LOG.warning(
                "No default actions defined and more than one service defined."
                "If one of the access path is / it will be used as default"
            )
            rules = handle_non_default_services(self, self.services)
            for rule in rules:
                template.add_resource(rule)
        else:
            raise ValueError(f"Failed to determine any default action for {self.title}")

    def handle_cognito_pools(self, settings, listener_stack):
        """

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ecs_composex.common.stacks.ComposeXStack listener_stack:
        :return:
        """
        cognito_auth_key = "AuthenticateCognitoConfig"
        for target in self.services:
            if keyisset("CreateCognitoClient", target):
                user_pool_client_params = target["CreateCognitoClient"]
                pool_id = user_pool_client_params["UserPoolId"]
                pool_params = import_cognito_pool(pool_id, settings, listener_stack)
                user_pool_client_params["UserPoolId"] = pool_params[0]
                user_pool_client_props = import_record_properties(
                    user_pool_client_params, UserPoolClient
                )
                user_pool_client = listener_stack.stack_template.add_resource(
                    UserPoolClient(
                        f"{listener_stack.title}UserPoolClient{NONALPHANUM.sub('', target['name'])}",
                        **user_pool_client_props,
                    )
                )
                if keyisset(cognito_auth_key, target):
                    target[cognito_auth_key]["UserPoolArn"] = pool_params[1]
                    target[cognito_auth_key]["UserPoolDomain"] = pool_params[2]
                    target[cognito_auth_key]["UserPoolClientId"] = Ref(user_pool_client)
                else:
                    LOG.warning(
                        "No AuthenticateCognitoConfig defined. Setting to default settings"
                    )
                    target.update(
                        {
                            cognito_auth_key: {
                                "OnUnauthenticatedRequest": "authenticate",
                                "Scope": "openid email profile",
                                "UserPoolArn": pool_params[1],
                                "UserPoolDomain": pool_params[2],
                                "UserPoolClientId": Ref(user_pool_client),
                            }
                        }
                    )
                del target["CreateCognitoClient"]
            elif (
                not keyisset("CreateCognitoClient", target)
                and keyisset(cognito_auth_key, target)
                and keyisset("UserPoolArn", target[cognito_auth_key])
                and target[cognito_auth_key]["UserPoolArn"].startswith("x-cognito")
            ):
                pool_id = target[cognito_auth_key]["UserPoolArn"].split(r"::")[-1]
                pool_params = import_cognito_pool(pool_id, settings, listener_stack)
                target[cognito_auth_key]["UserPoolArn"] = pool_params[1]
                target[cognito_auth_key]["UserPoolDomain"] = pool_params[2]

    def handle_certificates(self, settings, listener_stack):
        """
        Method to handle certificates

        :param ecs_composex.common.settings.ComposeXSettings settings:

        :return:
        """
        valid_sources = [
            ("x-acm", str, import_new_acm_certs),
            ("Arn", str, add_acm_certs_arn),
            ("CertificateArn", str, add_acm_certs_arn),
        ]
        if not keyisset("Certificates", self.definition):
            LOG.warning(f"No certificates defined for Listener {self.name}")
            return
        for cert_def in self.definition["Certificates"]:
            if isinstance(cert_def, dict):
                cert_source = list(cert_def.keys())[0]
                source_value = cert_def[cert_source]
                if cert_source not in [source[0] for source in valid_sources]:
                    raise KeyError(
                        "The certificate source can only defined from",
                        [source[0] for source in valid_sources],
                        "Got",
                        cert_source,
                    )
                for src_type in valid_sources:
                    if (
                        src_type[0] == cert_source
                        and isinstance(cert_source, src_type[1])
                        and src_type[2]
                    ):
                        src_type[2](self, source_value, settings, listener_stack)

    def validate_mapping(self, lb, t_targets, l_targets):
        """
        Method to validate the services mapping

        :param ecs_composex.elbv2.elbv2_stack.Elbv2 lb:
        :param list t_targets:
        :param list l_targets:
        :return:
        """
        if not all(target in t_targets for target in l_targets):
            raise KeyError(
                "Missing one of ",
                [
                    i
                    for i in l_targets + t_targets
                    if i not in l_targets or i not in t_targets
                ],
                f" in {lb.logical_name} Services for listener {self.title}",
            )

    def map_services(self, lb):
        """
        Map Services defined in LB definition to Targets

        :param ecs_composex.elbv2.elbv2_stack.Elbv2 lb:
        """
        if not self.services:
            return
        l_targets = [s["name"] for s in self.services]
        t_targets = [s["name"] for s in lb.services]
        self.validate_mapping(lb, t_targets, l_targets)
        for l_service_def in self.services:
            name = l_service_def["name"]
            map_service_target(lb, name, l_service_def)


def validate_service_def(service_def):
    required_settings = [
        ("name", str),
        ("port", int),
        ("healthcheck", str),
    ]
    if not all(
        prop in service_def.keys() for prop in [attr[0] for attr in required_settings]
    ):
        raise KeyError("For services you must at least define", required_settings)


class Elbv2(XResource):
    """
    Class to handle ELBv2 creation and mapping to ECS Services
    """

    subnets_param = APP_SUBNETS

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        if not keyisset("Listeners", definition):
            raise KeyError("You must specify at least one Listener for a LB.", name)
        self.lb_is_public = False
        self.lb_type = "application"
        self.ingress = None
        self.lb_sg = None
        self.lb_eips = []
        self.unique_service_lb = False
        self.lb = None
        self.listeners = []
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
        self.validate_services()
        self.sort_props()

    def init_outputs(self):
        self.output_properties = {
            LB_DNS_NAME: (
                f"{self.logical_name}{LB_DNS_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                LB_DNS_NAME.return_value,
            ),
            LB_DNS_ZONE_ID: (
                f"{self.logical_name}{LB_DNS_ZONE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                LB_DNS_ZONE_ID.return_value,
            ),
        }

    def set_listeners(self, template):
        """
        Method to define the listeners
        :return:
        """
        if not keyisset("Listeners", self.definition):
            raise KeyError(f"You must define at least one listener for LB {self.name}")
        ports = [listener["Port"] for listener in self.definition["Listeners"]]
        validate_listeners_duplicates(self.name, ports)
        for listener_def in self.definition["Listeners"]:
            new_listener = template.add_resource(ComposeListener(self, listener_def))
            self.listeners.append(new_listener)

    def set_services_targets(self, settings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        the_right_service = None
        if not self.services:
            LOG.info(f"No services defined for {self.name}")
            return
        for service_def in self.services:
            validate_service_def(service_def)
            family_combo_name = service_def["name"]
            service_name = family_combo_name.split(":")[-1]
            family_name = NONALPHANUM.sub("", family_combo_name.split(":")[0])
            LOG.info(f"Family {family_name} - Service {service_name}")
            if family_name not in settings.families:
                raise ValueError(
                    f"FamilyName {family_name} is invalid. Defined families",
                    settings.families.keys(),
                )
            for f_service in settings.families[family_name].services:
                if f_service.name == service_name:
                    the_right_service = f_service
                    break
            if not the_right_service:
                raise ValueError(
                    f"Could not find {service_name} in family {family_name}"
                )
            if (
                the_right_service in settings.services
                and the_right_service not in self.families_targets
            ):
                self.families_targets.append(
                    (
                        the_right_service,
                        the_right_service.my_family,
                        service_def,
                        f"{service_def['name']}{service_def['port']}",
                    )
                )
            elif the_right_service not in settings.services:
                raise ValueError(
                    "For elbv2, please, use only the services names."
                    "You cannot use the family name defined by deploy labels"
                    f"Found {the_right_service}",
                    [s for s in settings.services],
                    [f for f in settings.families],
                )
        self.debug_families_targets()

    def validate_services(self):
        allowed_keys = [
            ("name", str),
            ("port", int),
            ("healthcheck", str),
            ("protocol", str),
        ]
        for service in self.services:
            if not all(
                key in [attr[0] for attr in allowed_keys] for key in service.keys()
            ):
                raise KeyError(
                    "Only allowed keys allowed are",
                    [key[0] for key in allowed_keys],
                    "Got",
                    service.keys(),
                )
            for key in allowed_keys:
                if keyisset(key[0], service) and not isinstance(
                    service[key[0]], key[1]
                ):
                    raise TypeError(
                        f"{key} should be", key[1], "Got", type(service[key[0]])
                    )
        services_names = list(set([service["name"] for service in self.services]))
        if len(services_names) == 1:
            LOG.info(
                f"LB {self.name} only has a unique service. LB will be deployed with the service stack."
            )
            self.unique_service_lb = True

    def sort_props(self):
        self.lb_is_public = (
            True
            if (
                keyisset("Scheme", self.properties)
                and self.properties["Scheme"] == "internet-facing"
            )
            else False
        )
        self.lb_type = (
            "application"
            if not keyisset("Type", self.properties)
            else self.properties["Type"]
        )
        self.sort_sg()

    def sort_sg(self):
        if self.is_nlb():
            self.lb_sg = Ref(AWS_NO_VALUE)
        elif self.is_alb():
            self.lb_sg = SecurityGroup(
                f"{self.logical_name}SecurityGroup",
                GroupDescription=Sub(
                    f"SG for LB {self.logical_name} in ${{{AWS_STACK_NAME}}}"
                ),
                GroupName=Sub(
                    f"{self.logical_name}-{self.lb_type}-sg-${{{AWS_STACK_NAME}}}"
                ),
                VpcId=Ref(VPC_ID),
                Tags=Tags(Name=Sub(f"elbv2-{self.logical_name}-${{{AWS_STACK_NAME}}}")),
            )

    def sort_alb_ingress(self, settings, stack_template):
        """
        Method to handle Ingress to ALB
        """
        if (
            not self.parameters
            or (self.parameters and not keyisset("Ingress", self.parameters))
            or self.is_nlb()
        ):
            LOG.warning(
                "You defined ingress rules for a NLB. This is invalid. Define ingress rules at the service level."
            )
            return
        elif not self.parameters or (
            self.parameters and not keyisset("Ingress", self.parameters)
        ):
            LOG.warning(f"You did not define any Ingress rules for ALB {self.name}.")
            return
        ports = [listener["Port"] for listener in self.definition["Listeners"]]
        ports = set_service_ports(ports)
        self.ingress = Ingress(self.parameters["Ingress"], ports)
        if self.ingress and self.is_alb():
            self.ingress.set_aws_sources(
                settings, self.logical_name, GetAtt(self.lb_sg, "GroupId")
            )
            self.ingress.set_ext_sources_ingress(
                self.logical_name, GetAtt(self.lb_sg, "GroupId")
            )
            self.ingress.associate_aws_igress_rules(stack_template)
            self.ingress.associate_ext_igress_rules(stack_template)

    def define_override_subnets(self, subnets, settings):
        """
        Method to define the subnets overrides to use for the LB

        :param subnets: The original subnets to replace
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return: the subnet name to use
        :rtype: str
        """

        if isinstance(subnets, Ref):
            subnets = subnets.data["Ref"]
        if self.parameters and keyisset("Subnets", self.parameters):
            if not self.parameters["Subnets"] in settings.subnets_mappings.keys():
                raise KeyError(
                    f"The subnets indicated for {self.name} is not valid. Valid ones are",
                    settings.subnets_mappings.keys(),
                )
            subnets = self.parameters["Subnets"]
        return subnets

    def set_eips(self, settings):
        """

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if self.is_nlb() and self.lb_is_public:
            if settings.create_vpc:
                for public_az in settings.aws_azs:
                    self.lb_eips.append(
                        EIP(
                            f"{self.logical_name}Eip{public_az['ZoneName'].title().split('-')[-1]}",
                            Domain="vpc",
                        )
                    )
            else:
                subnets = self.define_override_subnets(PUBLIC_SUBNETS.title, settings)
                for public_az in settings.subnets_mappings[subnets]["Azs"]:
                    self.lb_eips.append(
                        EIP(
                            f"{self.logical_name}Eip{public_az.title().split('-')[-1]}",
                            Domain="vpc",
                        )
                    )

    def set_subnets(self, settings):
        """
        Method to define which subnets to use for the
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        subnets = APP_SUBNETS.title
        if self.is_nlb() and self.lb_is_public:
            subnets = Ref(AWS_NO_VALUE)
        elif (
            not self.lb_is_public
            and self.parameters
            and keyisset("Subnets", self.parameters)
        ):
            override_name = self.define_override_subnets(subnets, settings)
            if settings.create_vpc and override_name not in [
                PUBLIC_SUBNETS.title,
                APP_SUBNETS.title,
            ]:
                raise ValueError(
                    "When Compose-X creates the VPC, the only subnets you can define to use are",
                    [PUBLIC_SUBNETS.title, APP_SUBNETS.title],
                )
            elif (
                not settings.create_vpc
                and override_name in settings.subnets_mappings.keys()
            ):
                subnets = Ref(override_name)
        else:
            if self.is_alb() and self.lb_is_public:
                subnets = Ref(PUBLIC_SUBNETS)
            elif not self.lb_is_public:
                subnets = Ref(APP_SUBNETS)
        return subnets

    def set_subnet_mappings(self, settings):
        if not (self.is_nlb() and self.lb_is_public):
            return Ref(AWS_NO_VALUE)
        if not self.lb_eips and self.lb_is_public:
            self.set_eips(settings)
        mappings = []
        subnets = self.define_override_subnets(PUBLIC_SUBNETS.title, settings)
        for count, eip in enumerate(self.lb_eips):
            mappings.append(
                SubnetMapping(
                    AllocationId=GetAtt(eip, "AllocationId"),
                    SubnetId=Select(count, Ref(subnets)),
                )
            )
        return mappings

    def parse_attributes_settings(self):
        """
        Method to parse pre-defined settings for shortcuts

        :return: the lb attributes mappings
        :rtype: list
        """
        valid_settings = [
            ("timeout_seconds", int, handle_timeout_seconds, self.is_alb()),
            (
                "desync_mitigation_mode",
                str,
                handle_desync_mitigation_mode,
                self.is_alb(),
            ),
            (
                "drop_invalid_header_fields",
                bool,
                handle_drop_invalid_headers,
                self.is_alb(),
            ),
            ("http2", bool, handle_http2, self.is_alb()),
            ("cross_zone", bool, handle_cross_zone, self.is_nlb()),
        ]
        mappings = []
        for setting in valid_settings:
            if (
                keypresent(setting[0], self.parameters)
                and isinstance(self.parameters[setting[0]], setting[1])
                and setting[3]
            ):
                if setting[2] and setting[3]:
                    mappings.append(setting[2](self.parameters[setting[0]]))
                elif setting[3]:
                    mappings.append(
                        LoadBalancerAttributes(
                            Key=setting[0],
                            Value=str(self.parameters[setting[0]]),
                        )
                    )
        return mappings

    def set_lb_attributes(self):
        """
        Method to define the LB attributes

        :return: List of LB Attributes
        :rtype: list
        """
        attributes = []
        if keyisset("LoadBalancerAttributes", self.properties):
            for prop in self.properties["LoadBalancerAttributes"]:
                attributes.append(
                    LoadBalancerAttributes(
                        Key=prop,
                        Value=self.properties["LoadBalancerAttributes"][prop],
                    )
                )
        elif (
            not keyisset("LoadBalancerAttributes", self.definition) and self.parameters
        ):
            attributes = self.parse_attributes_settings()
        if attributes:
            return attributes
        return Ref(AWS_NO_VALUE)

    def set_lb_definition(self, settings):
        """
        Function to parse the LB settings and properties and build the LB object

        :param ecs_composex.elbv2.elbv2_stack.Elbv2 self:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        attrs = {
            "IpAddressType": "ipv4"
            if not keyisset("IpAddressType", self.properties)
            else self.properties["IpAddressType"],
            "Type": self.lb_type,
            "Scheme": "internet-facing" if self.lb_is_public else "internal",
            "SecurityGroups": [Ref(self.lb_sg)]
            if isinstance(self.lb_sg, SecurityGroup)
            else self.lb_sg,
            "Subnets": self.set_subnets(settings),
            "SubnetMappings": self.set_subnet_mappings(settings),
            "LoadBalancerAttributes": self.set_lb_attributes(),
            "Tags": Tags(Name=Sub(f"${{{ROOT_STACK_NAME.title}}}{self.logical_name}")),
            "Name": Ref(AWS_NO_VALUE),
        }
        self.lb = LoadBalancer(self.logical_name, **attrs)
        self.cfn_resource = self.lb

    def is_nlb(self):
        return True if self.lb_type == "network" else False

    def is_alb(self):
        return True if self.lb_type == "application" else False

    def associate_to_template(self, template):
        """
        Method to associate all resources to the template

        :param troposphere.Template template:
        :return:
        """
        template.add_resource(self.lb)
        if self.lb_sg and isinstance(self.lb_sg, SecurityGroup):
            template.add_resource(self.lb_sg)
            template.add_output(
                ComposeXOutput(
                    self.lb_sg,
                    [(LB_SG_ID, "", GetAtt(self.lb_sg, "GroupId"))],
                    export=False,
                ).outputs
            )
        for eip in self.lb_eips:
            template.add_resource(eip)


def init_elbv2_template():
    """
    Function to create a new root ELBv2 stack
    :return:
    """
    lb_params = [VPC_ID, APP_SUBNETS, PUBLIC_SUBNETS]
    template = build_template("elbv2 root template for ComposeX", lb_params)
    return template


class XStack(ComposeXStack):
    """
    Class to handle ELBv2 resources
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Elbv2, RES_KEY, MOD_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if lookup_resources or use_resources:
            warnings.warn(
                f"{RES_KEY} - Lookup not supported. You can only create new resources."
            )
        if not new_resources:
            self.is_void = True
            return
        stack_template = init_elbv2_template()
        lb_input = {
            VPC_ID.title: Ref(VPC_ID),
            APP_SUBNETS.title: Ref(APP_SUBNETS),
            PUBLIC_SUBNETS.title: Ref(PUBLIC_SUBNETS),
        }
        for resource in new_resources:
            resource.set_lb_definition(settings)
            resource.sort_alb_ingress(settings, stack_template)
        super().__init__(title, stack_template, stack_parameters=lb_input, **kwargs)
