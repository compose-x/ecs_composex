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
Module to create the root stack for DynamoDB tables
"""

from troposphere import Ref, GetAtt

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import set_resources, XResource
from ecs_composex.dynamodb.dynamodb_params import RES_KEY
from ecs_composex.dynamodb.dynamodb_template import create_dynamodb_template
from ecs_composex.dynamodb.dynamodb_params import TABLE_ARN, TABLE_NAME
from ecs_composex.dynamodb.dynamodb_perms import get_access_types


class Table(XResource):
    """
    Class to represent a DynamoDB Table
    """

    main_attr = TABLE_NAME
    arn_attr = TABLE_ARN
    policies_scaffolds = get_access_types()

    def __init__(self, name, definition, settings):
        super().__init__(name, definition, settings)
        self.name_export = None
        self.name_import = None
        self.arn_export = None
        self.arn_import = None
        self.arn_attr = TABLE_ARN

    def init_outputs(self):
        self.output_properties = {
            TABLE_NAME.title: (self.logical_name, self.cfn_resource, Ref, None),
            TABLE_ARN.title: (
                f"{self.logical_name}{TABLE_ARN.title}",
                self.cfn_resource,
                GetAtt,
                TABLE_ARN.title,
            ),
        }

    def set_outputs(self):
        """
        Method to set the outputs and imports settings.
        :return:
        """
        if not self.cfn_resource:
            return


class XStack(ComposeXStack):
    """
    Class for Dynamodb
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Table, RES_KEY)
        stack_template = create_dynamodb_template(settings)
        super().__init__(title, stack_template, **kwargs)
