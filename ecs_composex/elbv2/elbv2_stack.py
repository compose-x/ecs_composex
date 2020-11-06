#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to handle elbv2.
"""

import re

from json import dumps
from copy import deepcopy

from troposphere import Ref, Sub, GetAtt, Select
from troposphere import AWS_STACK_NAME, AWS_NO_VALUE

from troposphere.ec2 import SecurityGroup, EIP
from troposphere.elasticloadbalancingv2 import (
    LoadBalancer,
    LoadBalancerAttributes,
    SubnetMapping,
    Listener,
    ListenerRule,
    ListenerCertificate,
    Certificate,
    Action,
    Condition,
    RedirectConfig,
    ForwardConfig,
    FixedResponseConfig,
    HttpHeaderConfig,
    HostHeaderConfig,
    PathPatternConfig,
    TargetGroupTuple,
)

from ecs_composex.common import keyisset, keypresent, build_template
from ecs_composex.common import NONALPHANUM, LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.outputs import ComposeXOutput

from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.vpc.vpc_params import VPC_ID, PUBLIC_SUBNETS, APP_SUBNETS

from ecs_composex.elbv2.elbv2_params import RES_KEY, LB_SG_ID


def handle_cross_zone(value):
    return LoadBalancerAttributes(
        Key="load_balancing.cross_zone.enabled", Value=str(value)
    )


def handle_http2(value):
    return LoadBalancerAttributes(Key="routing.http2.enabled", Value=str(value))


def handle_drop_invalid_headers(value):
    return LoadBalancerAttributes(
        Key="routing.http.drop_invalid_header_fields.enabled", Value=str(value)
    )


def handle_desync_mitigation_mode(value):
    if value not in ["defensive", "strictest", "monitor"]:
        raise ValueError(
            "desync_mitigation_mode must be one of",
            ["defensive", "strictest", "monitor"],
        )
    return LoadBalancerAttributes(
        Key="routing.http.desync_mitigation_mode", Value=str(value)
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
        LOG.warn("No service path matches /. Defaulting to return TeaPot")
        listener.DefaultActions.append(tea_pot(True))
    elif default_target:
        listener.DefaultActions.append(
            Action(
                Type="forward",
                ForwardConfig=ForwardConfig(
                    TargetGroups=[
                        TargetGroupTuple(TargetGroupArn=default_target["target_arn"])
                    ]
                ),
            ),
        )
    rules = []
    for count, service_def in enumerate(left_services):
        rule = ListenerRule(
            f"{listener.title}{NONALPHANUM.sub('', service_def['name'])}Rule",
            ListenerArn=Ref(listener),
            Actions=[
                Action(
                    Type="forward",
                    ForwardConfig=ForwardConfig(
                        TargetGroups=[
                            TargetGroupTuple(TargetGroupArn=service_def["target_arn"])
                        ]
                    ),
                ),
            ],
            Priority=(count + 1),
            Conditions=define_target_conditions(service_def),
        )
        rules.append(rule)
    return rules


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

        :param ecs_composex.elbv2.elbv2_stack.elbv2 lb:
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
        self.handle_certificates()

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
            self.DefaultActions.insert(
                0,
                Action(
                    Type="forward",
                    ForwardConfig=ForwardConfig(
                        TargetGroups=[
                            TargetGroupTuple(
                                TargetGroupArn=self.services[0]["target_arn"]
                            )
                        ]
                    ),
                ),
            )
        elif not self.default_actions and self.services and len(self.services) > 1:
            LOG.warn(
                "No default actions defined and more than one service defined."
                "If one of the access path is / it will be used as default"
            )
            rules = handle_non_default_services(self, self.services)
            for rule in rules:
                template.add_resource(rule)
        else:
            raise ValueError(f"Failed to determine any default action for {self.title}")

    def handle_certificates(self):
        """
        Method to handle certificates
        :return:
        """
        valid_sources = [
            ("x-acm", str, None),
            ("Arn", str, None),
            ("CertificateArn", str, None),
        ]
        if not keyisset("Certificates", self.definition):
            LOG.warn(f"No certificates defined for Listener {self.name}")
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

    def map_services(self, lb):
        if not self.services:
            return
        l_targets = [s["name"] for s in self.services]
        t_targets = [s["name"] for s in lb.services]
        if not all(target in t_targets for target in l_targets):
            raise KeyError(
                f"Missing one of ",
                [
                    i
                    for i in l_targets + t_targets
                    if i not in l_targets or i not in t_targets
                ],
                f" in {lb.logical_name} Services for listener {self.title}",
            )
        for l_service_def in self.services:
            name = l_service_def["name"]
            for target in lb.families_targets:
                t_family = target[1].logical_name
                t_service = target[0].name
                target_name = f"{t_family}:{t_service}"
                if target_name == name:
                    for service in lb.services:
                        if service["name"] == target_name:
                            l_service_def["target_arn"] = service["target_arn"]
                            break
                    break


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


class elbv2(XResource):
    """
    Class to handle ELBv2 creation and mapping to ECS Services
    """

    def __init__(self, name, definition, settings):
        self.lb_is_public = False
        self.lb_type = "application"
        self.lb_sg = None
        self.lb_eips = []
        self.unique_service_lb = False
        self.lb = None
        self.listeners = []
        super().__init__(name, definition, settings)
        self.validate_services()
        self.sort_props()

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
            )

    def set_eips(self, settings):
        """

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if self.is_nlb() and self.lb_is_public:
            for public_az in settings.public_azs:
                self.lb_eips.append(
                    EIP(
                        f"{self.logical_name}Eip{public_az.title().split('-')[-1]}",
                        Domain="vpc",
                    )
                )

    def set_subnets(self):
        if self.is_nlb() and self.lb_is_public:
            return Ref(AWS_NO_VALUE)
        elif self.is_alb() and self.lb_is_public:
            return Ref(PUBLIC_SUBNETS)
        elif not self.lb_is_public:
            return Ref(APP_SUBNETS)

    def set_subnet_mappings(self, settings):
        if not (self.is_nlb() and self.lb_is_public):
            return Ref(AWS_NO_VALUE)
        if not self.lb_eips:
            self.set_eips(settings)
        mappings = []
        for count, eip in enumerate(self.lb_eips):
            mappings.append(
                SubnetMapping(
                    AllocationId=GetAtt(eip, "AllocationId"),
                    SubnetId=Select(count, Ref(PUBLIC_SUBNETS)),
                )
            )
        return mappings

    def parse_attributes_settings(self):
        """
        Method to parse pre-defined settings for shortcuts
        :return:
        """
        valid_settings = [
            ("timeout_seconds", int, None),
            ("desync_mitigation_mode", str, handle_desync_mitigation_mode),
            ("drop_invalid_header_fields", bool, handle_drop_invalid_headers),
            ("http2", bool, handle_http2),
            ("cross_zone", bool, handle_cross_zone),
        ]
        mappings = []
        for setting in valid_settings:
            if keypresent(setting[0], self.settings) and isinstance(
                self.settings[setting[0]], setting[1]
            ):
                if setting[2]:
                    mappings.append(setting[2](self.settings[setting[0]]))
                else:
                    mappings.append(
                        LoadBalancerAttributes(
                            Key=setting[0], Value=str(self.settings[setting[0]])
                        )
                    )
        return mappings

    def set_lb_attributes(self):
        """
        Method to define the LB attributes
        """
        attributes = []
        if keyisset("LoadBalancerAttributes", self.properties):
            for prop in self.properties["LoadBalancerAttributes"]:
                attributes.append(
                    LoadBalancerAttributes(
                        Key=prop, Value=self.properties["LoadBalancerAttributes"][prop]
                    )
                )
        elif not keyisset("LoadBalancerAttributes", self.definition) and self.settings:
            attributes = self.parse_attributes_settings()
        if attributes:
            return attributes
        return Ref(AWS_NO_VALUE)

    def set_lb_definition(self, settings):
        """
        Function to parse the LB settings and properties and build the LB object

        :param ecs_composex.elbv2.elbv2_stack.elbv2 self:
        :return:
        """
        attrs = {
            "IpAddressType": "ipv4"
            if not keyisset("IpAddressType", self.properties)
            else self.properties["IpAddressType"],
            "Name": Sub(f"${{{ROOT_STACK_NAME.title}}}{self.logical_name}"),
            "Type": self.lb_type,
            "Scheme": "internet-facing" if self.lb_is_public else "internal",
            "SecurityGroups": [Ref(self.lb_sg)]
            if isinstance(self.lb_sg, SecurityGroup)
            else self.lb_sg,
            "Subnets": self.set_subnets(),
            "SubnetMappings": self.set_subnet_mappings(settings),
            "LoadBalancerAttributes": self.set_lb_attributes(),
        }
        self.lb = LoadBalancer(self.logical_name, **attrs)

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
        set_resources(settings, elbv2, RES_KEY)
        resources = settings.compose_content[RES_KEY]
        new_resources = [
            resources[res_name]
            for res_name in resources
            if not resources[res_name].lookup
        ]
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
        super().__init__(title, stack_template, stack_parameters=lb_input, **kwargs)
