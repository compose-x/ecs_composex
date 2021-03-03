# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@compose-x.io>
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

from troposphere import Ref, GetAtt

from ecs_composex.common import build_template
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.rds.rds_features import apply_extra_parameters
from ecs_composex.rds.rds_params import DB_NAME, DB_ENDPOINT_PORT, DB_SECRET_ARN, DB_SG
from ecs_composex.rds.rds_params import MOD_KEY, RES_KEY
from ecs_composex.rds.rds_template import generate_rds_templates
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID


class Rds(XResource):
    """
    Class to represent a RDS DB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(self, name, definition, module_name, settings):
        self.db_secret = None
        self.db_sg = None
        self.db_subnet_group = None
        super().__init__(name, definition, module_name, settings)
        self.set_override_subnets()

    def init_outputs(self):
        """
        Method to init the RDS Output attributes
        """
        self.output_properties = {
            DB_NAME: (self.logical_name, self.cfn_resource, Ref, None, "DbName"),
            DB_ENDPOINT_PORT: (
                f"{self.logical_name}{DB_ENDPOINT_PORT}",
                self.cfn_resource,
                GetAtt,
                DB_ENDPOINT_PORT.return_value,
                DB_ENDPOINT_PORT.return_value.replace(r".", ""),
            ),
            DB_SECRET_ARN: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
                "SecretArn",
            ),
            DB_SG: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                DB_SG.return_value,
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
        set_resources(settings, Rds, RES_KEY, MOD_KEY)
        new_dbs = [
            db
            for db in settings.compose_content[RES_KEY].values()
            if not db.lookup and not db.use
        ]
        if new_dbs:
            stack_template = build_template(
                "Root stack for RDS DBs", [VPC_ID, STORAGE_SUBNETS]
            )
            super().__init__(title, stack_template, **kwargs)
            generate_rds_templates(stack_template, new_dbs, settings)
            self.mark_nested_stacks()
        else:
            self.is_void = True

        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
