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

from troposphere import GetAtt, Sub, Ref, If, Join, Tags
from troposphere.ec2 import SecurityGroup, SecurityGroupIngress

from ecs_composex.common import build_template, keyisset, LOG
from ecs_composex.common import load_composex_file, keypresent
from ecs_composex.common.cfn_conditions import USE_CLOUDMAP_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, USE_CLOUDMAP
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common.outputs import define_import
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import add_all_tags
from ecs_composex.common.tagging import generate_tags_parameters
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_NAME_T
from ecs_composex.ecs.ecs_template import generate_services
from ecs_composex.vpc import vpc_params


class ServiceStack(ComposeXStack):
    """
    Class to handle individual ecs_service stack
    """

    def __init__(
        self, title, template, service, template_file=None, extension=None, **kwargs
    ):
        self.service = service
        super().__init__(title, template, template_file, extension, **kwargs)
        if not keyisset("Parameters", kwargs):
            self.Parameters = {
                ROOT_STACK_NAME_T: Ref("AWS::StackName"),
                vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
                vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
                vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            }


class ServicesStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    vpc_stack = None
    dependencies = []
    services = []

    def __init__(self, title, template, template_file=None, extension=None, **kwargs):
        self.create_services_templates(**kwargs)
        super().__init__(title, self.stack_template, template_file, extension, **kwargs)
        if not keyisset("Parameters", kwargs):
            self.Parameters = {
                ROOT_STACK_NAME_T: Ref("AWS::StackName"),
                vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
                vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
                vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            }

    def handle_service_links(self, service):
        """
        Function to handle links between services
        :param service:
        """
        LOG.debug(f"Adding services link for {service.service_name}")
        for link in service.links:
            if link not in self.services:
                raise KeyError(f"{link} is not defined in the services of the template")
            dest_service = self.services[link]
            for port in dest_service.config.ports:
                SecurityGroupIngress(
                    f"From{service.resource_name}To{dest_service.resource_name}Port{port['target']}",
                    template=service.template,
                    SourceSecurityGroupOwnerId=Ref("AWS::AccountId"),
                    SourceSecurityGroupId=GetAtt(ecs_params.SG_T, "GroupId"),
                    IpProtocol=port["protocol"],
                    FromPort=port["target"],
                    ToPort=port["target"],
                    GroupId=define_import(
                        dest_service.resource_name, ecs_params.SERVICE_GROUP_ID_T
                    ),
                    Description=f"From{service.resource_name}To{dest_service.resource_name}Port{port['target']}",
                )
            if dest_service.resource_name not in service.dependencies:
                LOG.debug(
                    f"Adding new dependency from {service.service_name} to {dest_service.service_name}"
                )
                service.dependencies.append(dest_service.resource_name)
            else:
                LOG.debug(
                    f"Dependency between {service.service_name} to {dest_service.service_name} already exists"
                )

    def handle_services_dependencies(self):
        """
        Function to handle dependencies between services as per depends_on in compose file
        """
        for service_name in self.services:
            service = self.services[service_name]
            for count, depend in enumerate(service.dependencies):
                if depend in self.services:
                    LOG.debug(
                        f"Adding dependency for {depend} using name {self.services[depend].resource_name}"
                    )
                    service.dependencies[count] = self.services[depend].resource_name
            if service.links:
                self.handle_service_links(service)

    def add_vpc_stack(self, vpc_stack):
        if isinstance(vpc_stack, ComposeXStack):
            vpc = vpc_stack.title
        elif isinstance(vpc_stack, str):
            vpc = vpc_stack
        else:
            raise TypeError(
                f"vpc_stack must be of type", ComposeXStack, str, "got", type(vpc_stack)
            )
        self.Parameters.update(
            {
                vpc_params.VPC_ID_T: GetAtt(
                    vpc_stack, f"Outputs.{vpc_params.VPC_ID_T}"
                ),
                vpc_params.PUBLIC_SUBNETS_T: GetAtt(
                    vpc_stack, f"Outputs.{vpc_params.PUBLIC_SUBNETS_T}"
                ),
                vpc_params.APP_SUBNETS_T: GetAtt(
                    vpc_stack, f"Outputs.{vpc_params.APP_SUBNETS_T}"
                ),
                vpc_params.VPC_MAP_ID_T: If(
                    USE_CLOUDMAP_CON_T,
                    GetAtt(vpc_stack, f"Outputs.{vpc_params.VPC_MAP_ID_T}"),
                    Ref("AWS::NoValue"),
                ),
            }
        )
        if not hasattr(self, "DependsOn"):
            self.DependsOn = [vpc]
        else:
            self.DependsOn.append(vpc)

    def create_services_templates(self, **kwargs):
        """
        Function to create the services root template
        """
        if keypresent("DependsOn", kwargs):
            kwargs.pop("DependsOn")
        content = load_composex_file(kwargs[XFILE_DEST])
        tags_params = generate_tags_parameters(content)
        parameters = [
            CLUSTER_NAME,
            vpc_params.VPC_ID,
            vpc_params.PUBLIC_SUBNETS,
            vpc_params.APP_SUBNETS,
            vpc_params.VPC_MAP_ID,
            USE_CLOUDMAP,
            ecs_params.XRAY_IMAGE,
            ecs_params.LOG_GROUP_RETENTION,
        ]
        self.stack_template = build_template(
            "Root template for ECS Services", parameters
        )
        cluster_sg = self.stack_template.add_resource(
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
        self.services = generate_services(content, cluster_sg, **kwargs)
        self.handle_services_dependencies()
        for service_name in self.services:
            service = self.services[service_name]
            service.parameters.update(
                {ecs_params.LOG_GROUP_RETENTION_T: Ref(ecs_params.LOG_GROUP_RETENTION)}
            )
            self.stack_template.add_resource(
                ServiceStack(
                    service.resource_name,
                    template=service.template,
                    service=service,
                    Parameters=service.parameters,
                    DependsOn=service.dependencies,
                    **kwargs,
                )
            )
        add_all_tags(self.stack_template, tags_params)

    def add_cluster_parameter(self, cluster_param):
        self.Parameters.update(cluster_param)
