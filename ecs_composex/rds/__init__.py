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


def create_rds_template(settings):
    """
    Creates the CFN Troposphere template

    :param settings: Execution settings
    :type settings: ecs_composex.common.settings.ComposeXSettings

    :return: rds_tpl
    :rtype: troposphere.Template
    """
    if not keyisset(RES_KEY, settings.compose_content):
        warn(f"No {RES_KEY} found in the docker compose definition. Skipping")
        return None
    rds_tpl = generate_rds_templates(settings)
    LOG.debug(f"Template for {RES_KEY} validated by CFN.")
    return rds_tpl


class XResource(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    vpc_stack = None
    dependencies = []

    def add_cluster_parameter(self, cluster_param):
        self.Parameters.update(cluster_param)

    def __init__(self, title, stack_template, **kwargs):
        super().__init__(title, stack_template, **kwargs)
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
