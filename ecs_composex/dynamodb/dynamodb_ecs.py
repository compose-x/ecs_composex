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
Module to manage IAM policies to grant access to ECS Services to DynamodbTables
"""

from troposphere.dynamodb import Table

from ecs_composex.common import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dynamodb.dynamodb_aws import lookup_dyn_table
from ecs_composex.dynamodb.dynamodb_params import TABLE_ARN
from ecs_composex.dynamodb.dynamodb_perms import ACCESS_TYPES
from ecs_composex.resource_permissions import (
    apply_iam_based_resources,
)
from ecs_composex.resource_settings import (
    generate_resource_permissions,
)


def handle_new_tables(
    xresources,
    services_families,
    services_stack,
    res_root_stack,
    l_tables,
    nested=False,
):
    tables_r = []
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if isinstance(s_resources[resource_name], Table):
            tables_r.append(s_resources[resource_name].title)
        elif issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_tables(
                xresources,
                services_families,
                services_stack,
                s_resources[resource_name],
                l_tables,
                nested=True,
            )

    for table_name in xresources:
        if table_name in tables_r:
            table = xresources[table_name]
            table.generate_resource_envvars(TABLE_ARN)
            perms = generate_resource_permissions(
                table.logical_name, ACCESS_TYPES, TABLE_ARN
            )
            apply_iam_based_resources(
                table,
                services_families,
                services_stack,
                res_root_stack,
                perms,
                nested,
            )
            del l_tables[table_name]


def dynamodb_to_ecs(
    xresources, services_stack, services_families, res_root_stack, settings
):
    """
    Function to link the resource and the ECS Services.

    :param dict xresources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param dict services_families:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    l_tables = xresources.copy()
    handle_new_tables(
        xresources, services_families, services_stack, res_root_stack, l_tables
    )
    for table_name in l_tables:
        table = xresources[table_name]
        found_resources = lookup_dyn_table(settings.session, table.lookup["Tags"])
        if not found_resources:
            LOG.warning(
                f"404 not tables found with the provided tags was found in defintion {table_name}."
            )
            continue
        for found_table in found_resources:
            if table.properties:
                table.properties.update(found_table)
            else:
                table.properties = found_table
            perms = generate_resource_permissions(
                found_table["Name"], ACCESS_TYPES, TABLE_ARN, arn=found_table["Arn"]
            )
            apply_iam_based_resources(
                table,
                services_families,
                services_stack,
                res_root_stack,
                perms,
            )
