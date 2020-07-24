#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from ecs_composex.dynamodb.dynamodb_params import RES_KEY
from ecs_composex.common import keyisset, LOG, build_template, NONALPHANUM
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dynamodb.dynamodb_table import add_table_to_template

CFN_MAX_RESOURCES = 1


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
    if len(list(tables.keys())) <= CFN_MAX_RESOURCES:
        mono_template = True

    template = build_template("DynamoDB for ECS ComposeX")
    for table_name in tables:
        if mono_template:
            add_table_to_template(template, table_name, tables[table_name])
        else:
            table_res_name = NONALPHANUM.sub("", table_name)
            table_template = build_template(
                f"Template for DynamoDB table {table_res_name}"
            )
            add_table_to_template(table_template, table_name, tables[table_name])
            table_stack = ComposeXStack(table_res_name, stack_template=table_template)
            template.add_resource(table_stack)
    return template
