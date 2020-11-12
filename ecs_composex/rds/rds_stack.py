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

from troposphere import Parameter
from troposphere import Ref, GetAtt

from ecs_composex.common import LOG
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.rds.rds_params import (
    DB_NAME,
    DB_ENDPOINT_PORT,
    DB_SECRET_T,
    DB_SG_T,
    DB_ENGINE_NAME,
)
from ecs_composex.rds.rds_template import generate_rds_templates

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
    rds_tpl = generate_rds_templates(settings, new_dbs)
    LOG.debug(f"Template for {RES_KEY} validated by CFN.")
    return rds_tpl


class Rds(XResource):
    """
    Class to represent a RDS DB
    """

    def __init__(self, name, definition, settings):
        self.db_secret = DB_SECRET_T
        self.sg_id = DB_SG_T
        super().__init__(name, definition, settings)
        self.arn_attr = Parameter(DB_SECRET_T, Type="String")
        self.output_properties = {
            DB_NAME.title: (self.logical_name, Ref, None),
            DB_ENDPOINT_PORT: (
                f"{self.logical_name}{DB_ENDPOINT_PORT}",
                GetAtt,
                DB_ENDPOINT_PORT,
            ),
            self.arn_attr.title: (
                f"{self.logical_name}{self.arn_attr.title}",
                Ref,
                self.db_secret,
            ),
            DB_SG_T: (f"{self.logical_name}{DB_SG_T}", Ref, self.sg_id),
        }

    def uses_aurora(self):
        if not self.lookup and self.properties[DB_ENGINE_NAME.title].startswith(
            "aurora"
        ):
            return True
        return False


class XStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

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
        else:
            self.is_void = True
