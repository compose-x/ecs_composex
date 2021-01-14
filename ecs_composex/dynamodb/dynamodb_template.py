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
Module for DynamoDB to create the root template
"""

from troposphere import MAX_OUTPUTS

from ecs_composex.common import keyisset, build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dynamodb.dynamodb_params import RES_KEY
from ecs_composex.dynamodb.dynamodb_table import generate_table

CFN_MAX_OUTPUTS = MAX_OUTPUTS - 10


def create_dynamodb_template(settings):
    """
    Function to create the root DynamdoDB template.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    mono_template = False
    if not keyisset(RES_KEY, settings.compose_content):
        return None
    tables = settings.compose_content[RES_KEY]
    if len(list(tables.keys())) <= CFN_MAX_OUTPUTS:
        mono_template = True

    template = build_template("DynamoDB for ECS ComposeX")
    for table_name in tables:
        table = tables[table_name]
        generate_table(table)
        if table.cfn_resource:
            table.init_outputs()
            table.generate_outputs()
            if mono_template:
                template.add_resource(table.cfn_resource)
                template.add_output(table.outputs)
            elif not mono_template:
                table_template = build_template(
                    f"Template for DynamoDB table {table.title}"
                )
                table_template.add_resource(table)
                table_template.add_output(table.outputs)
                table_stack = ComposeXStack(
                    table.logical_name, stack_template=table_template
                )
                template.add_resource(table_stack)
    return template
