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
from ecs_composex.common import LOG, keyisset, NONALPHANUM
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.ecs.ecs_container_config import extend_container_envvars
from ecs_composex.ecs.ecs_params import TASK_ROLE_T
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.dynamodb.dynamodb_perms import (
    generate_dynamodb_permissions,
    generate_dynamodb_envvars,
)


def apply_settings_to_service(
    service_template, perms, env_vars, access_type, service_name, family_wide
):
    containers = define_service_containers(service_template)
    policy = perms[access_type]
    task_role = service_template.resources[TASK_ROLE_T]
    task_role.Policies.append(policy)
    for container in containers:
        if family_wide:
            extend_container_envvars(container, env_vars)
        elif not family_wide and container.Name == service_name:
            extend_container_envvars(container, env_vars)
            break


def dynamodb_to_ecs(
    tables, services_stack, services_families, dyndb_root_stack, **kwargs
):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    tables_r = []
    resources = dyndb_root_stack.stack_template.resources
    for resource_name in resources:
        if isinstance(resources[resource_name], Table):
            tables_r.append(resources[resource_name].title)

    for table_name, table_name_r in zip(tables, tables_r):
        table = tables[table_name]
        if table_name_r not in dyndb_root_stack.stack_template.resources:
            raise KeyError(
                f"Table {table_name} not a resource of the {dyndb_root_stack.title} stack"
            )
        elif (
            keyisset("Lookup", table)
            and table_name not in dyndb_root_stack.stack_template.resources
        ):
            lookup_dynamodb_table(table_name)

        perms = generate_dynamodb_permissions(table_name_r)
        envvars = generate_dynamodb_envvars(table_name_r, table)

        LOG.debug([var.Name for var in envvars])

        if perms and envvars and keyisset("Services", table):
            for service in table["Services"]:
                service_family = get_service_family_name(
                    services_families, service["name"]
                )
                family_wide = True if service["name"] in services_families else False
                if service_family not in services_stack.stack_template.resources:
                    raise KeyError(
                        f"Service {service_family} not in the services stack",
                        services_stack.stack_template.resources,
                    )
                service_stack = services_stack.stack_template.resources[service_family]
                apply_settings_to_service(
                    service_stack.stack_template,
                    perms,
                    envvars,
                    service["access"],
                    NONALPHANUM.sub("", service["name"]),
                    family_wide,
                )
            if dyndb_root_stack.title not in services_stack.DependsOn:
                services_stack.add_dependencies(dyndb_root_stack.title)
