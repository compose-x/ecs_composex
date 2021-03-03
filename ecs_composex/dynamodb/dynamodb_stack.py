#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@compose-x.io>
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

from ecs_composex.common import build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import set_resources, XResource
from ecs_composex.dynamodb.dynamodb_params import RES_KEY, MOD_KEY
from ecs_composex.dynamodb.dynamodb_template import create_dynamodb_template
from ecs_composex.dynamodb.dynamodb_params import TABLE_ARN, TABLE_NAME
from ecs_composex.dynamodb.dynamodb_perms import get_access_types


class Table(XResource):
    """
    Class to represent a DynamoDB Table
    """

    policies_scaffolds = get_access_types()

    def init_outputs(self):
        self.output_properties = {
            TABLE_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            TABLE_ARN: (
                f"{self.logical_name}{TABLE_ARN.title}",
                self.cfn_resource,
                GetAtt,
                TABLE_ARN.return_value,
            ),
        }


class XStack(ComposeXStack):
    """
    Class for Dynamodb
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Table, RES_KEY, MOD_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = [
            resource
            for resource in x_resources
            if (resource.properties or resource.parameters) and not resource.lookup
        ]
        if new_resources:
            stack_template = build_template("Root template for DynamoDB tables")
            super().__init__(title, stack_template, **kwargs)
            create_dynamodb_template(new_resources, stack_template, self)
        else:
            self.is_void = True
        for resource in x_resources:
            if resource.lookup:
                resource.stack = self
