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


from troposphere import Ref, Tags
from troposphere import dynamodb

from ecs_composex.common import LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.dynamodb import metadata
from ecs_composex.resources_import import import_record_properties


def define_table(table):
    """
    Function to create the DynamoDB table resource

    :param table:
    :type table: ecs_composex.common.compose_resources.Table
    """
    table_props = import_record_properties(table.properties, dynamodb.Table)
    table_props.update(
        {
            "Metadata": metadata,
            "Tags": Tags(
                Name=table.name,
                ResourceName=table.logical_name,
                CreatedByComposex=True,
                RootStackName=Ref(ROOT_STACK_NAME),
            ),
        }
    )
    cfn_table = dynamodb.Table(table.logical_name, **table_props)
    table.cfn_resource = cfn_table


def generate_table(table):
    """
    Function to add or lookup the DynamoDB table

    :param table:
    :type table: ecs_composex.common.compose_resources.Table
    :return: table
    :rtype: dynamodb.Table or None
    """
    if table.lookup:
        LOG.info("If table is found, its ARN will be added to the task")
        return
    if not table.properties:
        LOG.warning(f"Properties for table {table.name} were not defined. Skipping")
        return
    define_table(table)
    return table
