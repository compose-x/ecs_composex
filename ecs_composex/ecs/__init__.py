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

This module is going to parse each service and each x-resource key from the compose file
(hence ComposeX) and determine its

* ServiceDefinition
* TaskDefinition
* TaskRole
* ExecutionRole

It is going to also, based on the labels set in the compose file

* Add the service to Service Discovery via AWS CloudMap
* Add load-balancers to dispatch traffic to the microservice

"""

import boto3
from troposphere import GetAtt, Ref, Join

from ecs_composex.common import load_composex_file, KEYISSET
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_template import generate_services_templates
from ecs_composex.vpc import vpc_params


def create_services_templates(session=None, **kwargs):
    """
    :return:
    """
    if session is None:
        session = boto3.session.Session()
    content = load_composex_file(kwargs[XFILE_DEST])
    services_template = generate_services_templates(
        compose_content=content, session=session, **kwargs
    )
    return services_template


class ServicesStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    vpc_stack = None
    dependencies = []

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
            }
        )
        if not hasattr(self, "DependsOn"):
            self.DependsOn = [vpc]
        else:
            self.DependsOn.append(vpc)

    def add_cluster_parameter(self, cluster_param):
        self.Parameters.update(cluster_param)

    def __init__(self, title, template, template_file=None, extension=None, **kwargs):
        super().__init__(title, template, template_file, extension, **kwargs)
        if not KEYISSET("DependsOn", kwargs):
            self.DependsOn = []
        if not KEYISSET("Parameters", kwargs):
            self.Parameters = {
                ROOT_STACK_NAME_T: Ref("AWS::StackName"),
                vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
                vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
                vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            }
