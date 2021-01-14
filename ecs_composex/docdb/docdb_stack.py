#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
AWS DocumentDB entrypoint for ECS ComposeX
"""

from troposphere import Ref, GetAtt

from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.docdb.docdb_params import (
    RES_KEY,
    DOCDB_NAME,
    DOCDB_PORT,
    DOCDB_SECRET,
)
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS
from ecs_composex.docdb.docdb_template import create_docdb_template


class DocDb(XResource):
    """
    Class to manage DocDB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(self, name, definition, settings):
        """
        Init method

        :param str name:
        :param dict definition:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.db_secret = None
        self.db_sg = None
        self.db_subnets_group = None
        super().__init__(name, definition, settings)
        self.arn_attr = DOCDB_SECRET
        self.set_override_subnets()

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            DOCDB_NAME.title: (self.logical_name, self.cfn_resource, Ref, None),
            DOCDB_PORT.title: (
                f"{self.logical_name}{DOCDB_PORT.title}",
                self.cfn_resource,
                GetAtt,
                DOCDB_PORT.title,
            ),
            self.db_secret.title: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
            ),
            self.db_sg.title: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                "GroupId",
            ),
        }


class XStack(ComposeXStack):
    """
    Class for the Stack of DocDB
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, DocDb, RES_KEY)
        new_resources = [
            settings.compose_content[RES_KEY][res_name]
            for res_name in settings.compose_content[RES_KEY]
            if not settings.compose_content[RES_KEY][res_name].lookup
        ]
        if new_resources:
            stack_template = create_docdb_template(new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
