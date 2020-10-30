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

from troposphere import Ref, Sub, GetAtt, Select
from troposphere import AWS_STACK_NAME, AWS_NO_VALUE

from troposphere.ec2 import SecurityGroup, EIP
from troposphere.elasticloadbalancingv2 import (
    LoadBalancer,
    LoadBalancerAttributes,
    SubnetMapping,
)

from ecs_composex.common import keyisset, keypresent
from ecs_composex.common import NONALPHANUM, LOG

from ecs_composex.common.compose_resources import XResource
from ecs_composex.vpc.vpc_params import VPC_ID, PUBLIC_SUBNETS, APP_SUBNETS

from ecs_composex.elbv2.elbv2_params import RES_KEY


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


class elbv2(XResource):
    """
    Class to handle ELBv2 creation and mapping to ECS Services
    """

    def __init__(self, name, definition, settings):
        self.lb_is_public = False
        self.lb_type = "application"
        self.lb_sg = None
        self.lb_eips = []
        self.lb = None
        super().__init__(name, definition, settings)
        self.validate_services()
        self.sort_props()

    def handle_families_targets_expansion(self, service, settings):
        the_service = [s for s in settings.services if s.name == service["name"]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [the_service],
                        service,
                    )
                )

    def set_services_targets(self, settings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            LOG.info(f"No services defined for {self.name}")
            return
        for service in self.services:
            service_name = service["name"]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (settings.families[service_name], True, [], service)
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.warn(f"The family {service_name} has already been added. Skipping")
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion(service, settings)
        self.debug_families_targets()

    def validate_services(self):
        allowed_keys = [
            ("name", str),
            ("access", str),
            ("port", int),
            ("default", bool),
            ("healthcheck", str),
        ]
        for service in self.services:
            if not all(
                key in [attr[0] for attr in allowed_keys] for key in service.keys()
            ):
                raise KeyError(
                    "Only allowed keys allowed are", [key[0] for key in allowed_keys]
                )
            for key in allowed_keys:
                if keyisset(key[0], service) and not isinstance(
                    service[key[0]], key[1]
                ):
                    raise TypeError(
                        f"{key} should be", key[1], "Got", type(service[key[0]])
                    )

    def sort_props(self):
        self.lb_is_public = (
            True
            if (
                keyisset("Scheme", self.properties)
                and self.properties["Scheme"] == "public-facing"
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
            "Name": self.logical_name,
            "Type": self.lb_type,
            "Scheme": "public-facing" if self.lb_is_public else "internal",
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
        for eip in self.lb_eips:
            template.add_resource(eip)
