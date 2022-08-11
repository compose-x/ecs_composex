#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import re
from copy import deepcopy
from json import dumps

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, FindInMap, Ref
from troposphere.elasticloadbalancingv2 import (
    Action,
    AuthenticateCognitoConfig,
    AuthenticateOidcConfig,
    Certificate,
    Condition,
    FixedResponseConfig,
    ForwardConfig,
    HostHeaderConfig,
    ListenerCertificate,
    ListenerRule,
    ListenerRuleAction,
    LoadBalancerAttributes,
    PathPatternConfig,
    RedirectConfig,
    TargetGroupTuple,
)

import ecs_composex.common.troposphere_tools
from ecs_composex.acm.acm_params import RES_KEY as ACM_KEY
from ecs_composex.cognito_userpool.cognito_params import MAPPINGS_KEY as COGNITO_MAP
from ecs_composex.cognito_userpool.cognito_params import RES_KEY as COGNITO_KEY
from ecs_composex.cognito_userpool.cognito_params import (
    USERPOOL_ARN,
    USERPOOL_DOMAIN,
    USERPOOL_ID,
)
from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    Parameter,
    add_parameters,
    add_update_mapping,
)
from ecs_composex.elbv2.elbv2_params import RES_KEY
from ecs_composex.resources_import import import_record_properties


def handle_cross_zone(value: str) -> LoadBalancerAttributes:
    """
    Handles MacroParamters for cross-zone.
    """
    return LoadBalancerAttributes(
        Key="load_balancing.cross_zone.enabled", Value=str(value).lower()
    )


def handle_http2(value: str) -> LoadBalancerAttributes:
    """
    Handles MacroParamters for HTTP2.
    """
    return LoadBalancerAttributes(Key="routing.http2.enabled", Value=str(value).lower())


def handle_drop_invalid_headers(value) -> LoadBalancerAttributes:
    """
    Handles MacroParamters for drop invalid headers.
    """
    return LoadBalancerAttributes(
        Key="routing.http.drop_invalid_header_fields.enabled",
        Value=str(value).lower(),
    )


def handle_desync_mitigation_mode(value) -> LoadBalancerAttributes:
    """
    Handles MacroParamters for desync mitigation.
    """
    if value not in ["defensive", "strictest", "monitor"]:
        raise ValueError(
            "desync_mitigation_mode must be one of",
            ["defensive", "strictest", "monitor"],
        )
    return LoadBalancerAttributes(
        Key="routing.http.desync_mitigation_mode", Value=str(value).lower()
    )


def handle_timeout_seconds(timeout_seconds) -> LoadBalancerAttributes:
    """
    Handles MacroParamters for timeout.
    """
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


def validate_listeners_duplicates(name, ports) -> None:
    """
    Ensures values are correct for ports used in Listeners

    :param name:
    :param ports:
    :return:
    """
    if len(ports) != len(set(ports)):
        s = set()
        raise ValueError(
            f"{name} - More than one listener with port {set(x for x in ports if x in s or s.add(x))}"
        )


def add_listener_certificate_via_arn(
    listener_stack, listener, certificate_arn_id, cert_name
) -> None:
    """
    Adds a new ListenerCertificate for a given listener.

    ListenerCertificate can only take 1 certificate in the list !!

    :param ecs_composex.common.stacks.ComposeXStack listener_stack:
    :param ecs_composex.elbv2.elbv2_stack.elbv2_listener.ComposeListener listener:
    :param str certificate_arn_id: the ID to point to the certificate
    :param str cert_name:

    """
    listener_stack.stack_template.add_resource(
        ListenerCertificate(
            f"AcmCert{listener.title}{NONALPHANUM.sub('', cert_name)}",
            Certificates=[Certificate(CertificateArn=certificate_arn_id)],
            ListenerArn=Ref(listener),
        )
    )


def http_to_https_default(default_of_all=False) -> Action:
    """
    Predefined rule to redirect HTTP to HTTPS
    """
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


def tea_pot(default_of_all=False) -> Action:
    """
    Predefined reply for ALB config rule, returning HTTP Tea Pot
    """
    return Action(
        FixedResponseConfig=FixedResponseConfig(
            ContentType="application/json",
            MessageBody=dumps({"Info": "Be our guest"}),
            StatusCode="418",
        ),
        Type="fixed-response",
        Order=Ref(AWS_NO_VALUE) if not default_of_all else 50000,
    )


def handle_predefined_redirects(listener, action_name) -> None:
    """
    Function to handle predefined redirects
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


def handle_default_actions(listener) -> None:
    """
    Handles default actions set on the listener
    """
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


def handle_string_condition_format(access_string) -> list:
    """
    Function to parse and understand what type of condition that is.
    Uses the *Access* parameter of the Target inside a Listener
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
    path_re = re.compile(r"(^/[\S]+$)")
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
                HostHeaderConfig=HostHeaderConfig(Values=[access_string]),
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


def define_target_conditions(definition) -> list:
    """
    Function to create the conditions for forward to target

    :param definition:
    :return: list of conditions
    :rtype: list
    """
    conditions = []
    if keyisset("Conditions", definition) and isinstance(
        definition["Conditions"], list
    ):
        conditions = import_record_properties(
            {"Conditions": definition["Conditions"]},
            ListenerRule,
            set_to_novalue=False,
            ignore_missing_required=True,
        )["Conditions"]
    elif keyisset("access", definition) and isinstance(definition["access"], str):
        return handle_string_condition_format(definition["access"])
    return conditions


def define_actions(listener, target_def, rule_actions: bool = False) -> list:
    """
    Function to identify the Target definition and create the resulting rule appropriately.

    :param dict target_def:
    :param ecs_composex.elbv2.elbv2_stack.elbv2_listener.ComposeListener listener:
    :param rule_actions: Whether to use Action or ListenerRuleAction
    :return: The action to add or action list for default target
    """
    action_class = Action if not rule_actions else ListenerRuleAction
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
        auth_action = action_class(
            Type=auth_action_type, AuthenticateCognitoConfig=auth_rule, Order=1
        )
    elif keyisset("AuthenticateOidcConfig", target_def):
        auth_action_type = "authenticate-oidc"
        props = import_record_properties(
            target_def["AuthenticateOidcConfig"], AuthenticateOidcConfig
        )
        auth_rule = AuthenticateOidcConfig(**props)
        auth_action = action_class(
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
            action_class(
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
            action_class(
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


def define_listener_rules_actions(listener, left_services) -> list:
    """
    Function to identify the Target definition and create the resulting rule appropriately.

    :param listener:
    :param list left_services:
    :return: The action to add or action list for default target
    """
    rules = []
    for count, service_def in enumerate(left_services):
        rule = ListenerRule(
            f"{listener.title}{NONALPHANUM.sub('', service_def['name'])}Rule",
            ListenerArn=Ref(listener),
            Actions=define_actions(listener, service_def, True),
            Priority=(count + 1),
            Conditions=define_target_conditions(service_def),
        )
        rules.append(rule)
    return rules


def handle_non_default_services(listener, services_def) -> list:
    """
    Function to handle define the listener rule and identify
    :param listener:
    :param services_def:
    :return:
    """
    left_services = deepcopy(services_def)
    for count, service_def in enumerate(services_def):
        if isinstance(service_def["access"], str) and service_def["access"] == "/":
            left_services.pop(count)
            listener.DefaultActions += define_actions(listener, service_def)
            break
    else:
        LOG.warning("No service path matches /. Defaulting to return TeaPot")
        listener.DefaultActions.append(tea_pot(True))

    rules = define_listener_rules_actions(listener, left_services)
    return rules


def add_extra_certificate(listener_stack, listener, cert_arn):
    """
    Function to add Certificates to listener

    :param listener_stack: The stack that "owns" the listener.
    :param listener: The listener to add the certificate to
    :param cert_arn: The identifier of the certificate
    """
    cert_arn_re = re.compile(
        r"((?:^arn:aws(?:-[a-z]+)?:acm:[\S]+:[0-9]+:certificate/)"
        r"([a-z0-9]{8}(?:-[a-z0-9]{4}){3}-[a-z0-9]{12})$)"
    )
    if cert_arn_re.match(cert_arn):
        cert_arn_id = cert_arn
    elif isinstance(cert_arn, str) and cert_arn.find(ACM_KEY) < 0:
        cert_arn_id = f"{ACM_KEY}::{cert_arn}"
    elif isinstance(cert_arn, str) and cert_arn.find(ACM_KEY):
        cert_arn_id = cert_arn
    else:
        raise ValueError(
            f"{listener_stack.title} - Certificate value is not valid", cert_arn
        )
    if hasattr(listener, "Certificates") and listener.Certificates:
        add_listener_certificate_via_arn(
            listener_stack, listener, cert_arn_id, cert_arn
        )
    else:
        setattr(listener, "Certificates", [Certificate(CertificateArn=cert_arn_id)])


def upgrade_listener_to_use_tls(listener):
    """
    Function to rectify the listener type when adding cert

    :param ecs_composex.elbv2.elbv2_stack.elbv2_listener.ComposeListener listener:
    :raises: ValueError if trying to set TLS for UDP
    """
    alb_protocols = ["HTTP", "HTTPS"]
    nlb_protocols = ["TCP", "UDP", "TCP_UDP", "TLS"]
    if listener.Protocol in alb_protocols and listener.Protocol == "HTTP":
        LOG.warning(
            f"{RES_KEY}.{listener.name} - Protocol is HTTP but certificate(s) defined. Updating to to HTTPS"
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
    if not keyisset(src_name, settings.compose_content[ACM_KEY]):
        raise ValueError(
            f"{listener_stack.title} - {ACM_KEY} - no certificate {src_name} found"
        )
    add_extra_certificate(listener_stack, listener, src_name)
    upgrade_listener_to_use_tls(listener)


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
        add_update_mapping(
            listener_stack.stack_template,
            the_pool.module.mapping_key,
            settings.mappings[the_pool.module.mapping_key],
        )
        return (
            FindInMap(COGNITO_MAP, the_pool.logical_name, USERPOOL_ID.title),
            FindInMap(COGNITO_MAP, the_pool.logical_name, USERPOOL_ARN.return_value),
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
    LOG.debug(
        f"{RES_KEY}.{listener.name} - Adding new ACM Certificate from defined ARN {src_value}"
    )
    add_extra_certificate(listener_stack, listener, src_value)
    upgrade_listener_to_use_tls(listener)


def map_service_target(lb, name, l_service_def):
    """
    Function to iterate over targets to map the service and its defined TargetGroup ARN

    :param ecs_composex.elbv2.elbv2_stack.elbv2.Elbv2 lb:
    :param str name:
    :param dict l_service_def:
    :return:
    """
    for target in lb.families_targets:
        t_family = target[0].name
        t_service = target[1].name
        target_name = f"{t_family}:{t_service}"
        if target_name == name:
            for service in lb.services:
                if service["name"] == target_name:
                    l_service_def["target_arn"] = service["target_arn"]
                    break
            break
