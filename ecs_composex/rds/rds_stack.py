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
from warnings import warn

from ecs_composex.common import LOG, keyisset
from ecs_composex.rds.rds_template import generate_rds_templates
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import XResource, set_resources

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


class Rds(XResource):
    """
    Class to represent a RDS DB
    """

    def __init__(self, name, definition):
        super().__init__(name, definition)


class XStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Rds, RES_KEY)
        template = create_rds_template(settings)
        super().__init__(title, stack_template=template, **kwargs)
