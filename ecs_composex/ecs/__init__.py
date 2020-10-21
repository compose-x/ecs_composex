# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Core module for ECS ComposeX.

This module is going to parse each ecs_service and each x-resource key from the compose file
(hence ComposeX) and determine its

* ServiceDefinition
* TaskDefinition
* TaskRole
* ExecutionRole

It is going to also, based on the labels set in the compose file

* Add the ecs_service to Service Discovery via AWS CloudMap
* Add load-balancers to dispatch traffic to the microservice

"""

from troposphere import Sub, Ref, Join, Tags
from troposphere.ec2 import SecurityGroup

from ecs_composex.common import build_template
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dns import dns_params
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.ecs.ecs_template import generate_services
from ecs_composex.vpc import vpc_params
from ecs_composex import __version__ as version

metadata = {
    "Type": "ComposeX",
    "Properties": {"ecs_composex::module": "ecs_composex.ecs", "Version": version},
}


class ServiceStack(ComposeXStack):
    """
    Class to handle individual ecs_service stack
    """

    def __init__(
        self,
        title,
        template,
        parameters,
    ):
        super().__init__(title, stack_template=template, stack_parameters=parameters)
        self.Parameters.update(
            {
                vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
                vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
                vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            }
        )
        self.Parameters.update(parameters)
        self.stack_template.set_metadata(metadata)


class ServicesStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    vpc_stack = None
    dependencies = []
    services = []

    def __init__(self, title, settings, **cfn_params):
        parameters = [
            CLUSTER_NAME,
            vpc_params.VPC_ID,
            vpc_params.PUBLIC_SUBNETS,
            vpc_params.APP_SUBNETS,
            ecs_params.XRAY_IMAGE,
            dns_params.PUBLIC_DNS_ZONE_NAME,
            dns_params.PUBLIC_DNS_ZONE_ID,
            dns_params.PRIVATE_DNS_ZONE_ID,
            dns_params.PRIVATE_DNS_ZONE_NAME,
        ]
        template = build_template("Root template for ECS Services", parameters)
        generate_services(settings)
        super().__init__(
            title,
            stack_template=template,
            **cfn_params,
        )
        self.create_services_templates(settings)
        if not settings.create_vpc:
            self.no_vpc_parameters()
        self.stack_template.set_metadata(metadata)

    def create_services_templates(self, settings):
        """
        Function to create the services root template
        """

        for family_name in settings.families:
            family = settings.families[family_name]
            self.stack_template.add_resource(
                ServiceStack(
                    title=family.logical_name,
                    template=family.template,
                    parameters=family.stack_parameters,
                )
            )
