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
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, USE_CLOUDMAP
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_NAME_T
from ecs_composex.ecs.ecs_template import generate_services
from ecs_composex.vpc import vpc_params


class ServiceStack(ComposeXStack):
    """
    Class to handle individual ecs_service stack
    """

    def __init__(
        self, title, template, parameters, service, service_config,
    ):
        self.service = service
        self.config = service_config
        super().__init__(title, stack_template=template, stack_parameters=parameters)
        self.Parameters.update(
            {
                ROOT_STACK_NAME_T: Ref("AWS::StackName"),
                vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
                vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
                vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            }
        )
        self.Parameters.update(parameters)


class ServicesStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    vpc_stack = None
    dependencies = []
    services = []

    def __init__(self, title, settings):
        parameters = [
            CLUSTER_NAME,
            vpc_params.VPC_ID,
            vpc_params.PUBLIC_SUBNETS,
            vpc_params.APP_SUBNETS,
            vpc_params.VPC_MAP_ID,
            vpc_params.VPC_MAP_DNS_ZONE,
            USE_CLOUDMAP,
            ecs_params.XRAY_IMAGE,
            ecs_params.LOG_GROUP_RETENTION,
        ]
        template = build_template("Root template for ECS Services", parameters)
        default_params = {ROOT_STACK_NAME_T: Ref("AWS::StackName")}
        cluster_sg = template.add_resource(
            SecurityGroup(
                "ClusterWideSecurityGroup",
                GroupDescription=Sub(f"SG for ${{{CLUSTER_NAME_T}}}"),
                GroupName=Sub(f"cluster-${{{CLUSTER_NAME_T}}}"),
                Tags=Tags(
                    {
                        "Name": Sub(f"clustersg-${{{CLUSTER_NAME_T}}}"),
                        "ClusterName": Ref(CLUSTER_NAME),
                    }
                ),
                VpcId=Ref(vpc_params.VPC_ID),
            )
        )
        services = generate_services(settings, cluster_sg)
        super().__init__(
            title, stack_template=template, stack_parameters=default_params,
        )
        self.create_services_templates(services)
        if not settings.create_vpc:
            self.no_vpc_parameters()

    def create_services_templates(self, services):
        """
        Function to create the services root template
        """

        for service_name in services:
            service = services[service_name]
            service.parameters.update(
                {ecs_params.LOG_GROUP_RETENTION_T: Ref(ecs_params.LOG_GROUP_RETENTION)}
            )
            self.stack_template.add_resource(
                ServiceStack(
                    title=service.resource_name,
                    service_config=service.config,
                    template=service.template,
                    service=service,
                    parameters=service.parameters,
                )
            )
