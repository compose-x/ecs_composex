# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

from troposphere import Parameter
from troposphere import Ref, GetAtt

from ecs_composex.common import LOG
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.rds.rds_params import (
    DB_NAME,
    DB_ENDPOINT_PORT,
    DB_SECRET_T,
)
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS
from ecs_composex.rds.rds_template import generate_rds_templates
from ecs_composex.rds.rds_features import apply_extra_parameters

RES_KEY = f"x-{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}"
RDS_SSM_PREFIX = f"/{RES_KEY}/"


def create_rds_template(settings, new_dbs):
    """
    Creates the CFN Troposphere template

    :param settings: Execution settings
    :type settings: ecs_composex.common.settings.ComposeXSettings

    :return: rds_tpl
    :rtype: troposphere.Template
    """
    rds_tpl = generate_rds_templates(new_dbs, settings)
    LOG.debug(f"Template for {RES_KEY} validated by CFN.")
    return rds_tpl


class Rds(XResource):
    """
    Class to represent a RDS DB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(self, name, definition, settings):
        self.db_secret = None
        self.db_sg = None
        self.db_subnet_group = None
        super().__init__(name, definition, settings)
        self.arn_attr = Parameter(DB_SECRET_T, Type="String")
        self.set_override_subnets()

    def init_outputs(self):
        """
        Method to init the RDS Output attributes
        """
        self.output_properties = {
            DB_NAME.title: (self.logical_name, self.cfn_resource, Ref, None, "DbName"),
            DB_ENDPOINT_PORT: (
                f"{self.logical_name}{DB_ENDPOINT_PORT}",
                self.cfn_resource,
                GetAtt,
                DB_ENDPOINT_PORT,
                "Port",
            ),
            self.db_secret.title: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
                "SecretArn",
            ),
            self.db_sg.title: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                "GroupId",
                "RdsDbSecurityGroup",
            ),
        }


class XStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    def add_xdependencies(self, root_stack, settings):
        """
        Method to handle RDS to other x- resources links.

        :param ComposeXStack root_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        for name, stack in self.stack_template.resources.items():
            db = stack.db
            if db.parameters:
                apply_extra_parameters(settings, stack, db, stack.stack_template)

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Rds, RES_KEY)
        new_dbs = [
            settings.compose_content[RES_KEY][db_name]
            for db_name in settings.compose_content[RES_KEY]
            if not settings.compose_content[RES_KEY][db_name].lookup
        ]
        if new_dbs:
            template = create_rds_template(settings, new_dbs)
            super().__init__(title, stack_template=template, **kwargs)
            self.mark_nested_stacks()
        else:
            self.is_void = True
