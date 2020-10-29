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

from ecs_composex.common import keyisset
from ecs_composex.common import NONALPHANUM

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import XResource, set_resources

from ecs_composex.vpc.vpc_params import VPC_ID, PUBLIC_SUBNETS, APP_SUBNETS

from ecs_composex.elbv2.elbv2_params import RES_KEY
from ecs_composex.elbv2.elbv2_template import generate_elbv2_template


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
        print(map)
        return mappings

    def set_lb_definition(self, settings):
        """
        Function to parse the LB settings and properties and build the LB object

        :param ecs_composex.elbv2.elbv2_stack.elbv2 self:
        :return:
        """
        attrs = {
            "Name": self.logical_name,
            "Type": self.lb_type,
            "Scheme": "public-facing" if self.lb_is_public else "internal",
            "SecurityGroups": [Ref(self.lb_sg)]
            if isinstance(self.lb_sg, SecurityGroup)
            else self.lb_sg,
            "Subnets": self.set_subnets(),
            "SubnetMappings": self.set_subnet_mappings(settings),
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
            print(self.name, self.lb_sg)
            template.add_resource(self.lb_sg)
        for eip in self.lb_eips:
            template.add_resource(eip)


class XStack(ComposeXStack):
    """
    Class to present the ELBv2 root stack
    """

    def __init__(self, title, settings, **kwargs):
        """
        Init ELBv2 stack

        :param str title: title for the new root stack
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        set_resources(settings, elbv2, RES_KEY)
        resources = settings.compose_content[RES_KEY]
        if [
            resources[res_name]
            for res_name in resources
            if not resources[res_name].lookup
        ]:
            stack_template = generate_elbv2_template(settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
