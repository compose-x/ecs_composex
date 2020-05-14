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
Module to handle AWS RDS CFN Templates creation
"""

import os
import boto3
from warnings import warn
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common import (
    validate_input,
    validate_kwargs,
    load_composex_file,
    LOG,
    keyisset,
)
from troposphere import GetAtt, Ref, Join
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.rds.rds_template import generate_rds_templates
from ecs_composex.vpc import vpc_params
from ecs_composex.common.stacks import ComposeXStack

RES_KEY = f"x-{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}"
RDS_SSM_PREFIX = f"/{RES_KEY}/"


def create_rds_template(session=None, **kwargs):
    """
    Creates the CFN Troposphere template

    :param session: boto3 session to override default
    :type session: boto3.session.Session

    :return: rds_tpl
    :rtype: troposphere.Template
    """
    content = load_composex_file(kwargs[XFILE_DEST])
    if not keyisset(RES_KEY, content):
        warn(f"No {RES_KEY} found in the docker compose definition. Skipping")
        return None
    validate_input(content, RES_KEY)
    validate_kwargs(["BucketName"], kwargs)

    if session is None:
        session = boto3.session.Session()
    rds_tpl = generate_rds_templates(compose_content=content, session=session, **kwargs)
    LOG.debug(f"Template for {RES_KEY} validated by CFN.")
    return rds_tpl


class XResource(ComposeXStack):
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
                vpc_params.STORAGE_SUBNETS_T: GetAtt(
                    vpc_stack, f"Outputs.{vpc_params.STORAGE_SUBNETS_T}"
                ),
            }
        )
        if not hasattr(self, "DependsOn"):
            self.DependsOn = [vpc]
        else:
            self.DependsOn.append(vpc)

    def add_cluster_parameter(self, cluster_param):
        self.Parameters.update(cluster_param)

    def __init__(
        self, title, stack_template, template_file=None, extension=None, **kwargs
    ):
        super().__init__(title, stack_template, template_file, extension, **kwargs)
        if not keyisset("DependsOn", kwargs):
            self.DependsOn = []
        if not keyisset("Parameters", kwargs):
            self.Parameters = {
                ROOT_STACK_NAME_T: Ref("AWS::StackName"),
                vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
                vpc_params.STORAGE_SUBNETS_T: Join(
                    ",", Ref(vpc_params.STORAGE_SUBNETS)
                ),
            }
