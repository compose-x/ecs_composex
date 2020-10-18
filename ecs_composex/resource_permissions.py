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
Module to handle permissions from x-resource to ECS service
"""

from ecs_composex.common import NONALPHANUM, LOG
from ecs_composex.ecs.ecs_container_config import extend_container_envvars
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.ecs.ecs_params import TASK_ROLE_T
from ecs_composex.ecs.ecs_template import get_service_family_name


def add_iam_policy_to_service_task_role(
    service_template, resource, perms, access_type, service_name, family_wide
):
    """
    Function to expand the ECS Task Role policy with the permissions for the resource
    :param troposphere.Template service_template:
    :param resource:
    :param perms:
    :param access_type:
    :param service_name:
    :param family_wide:
    :return:
    """
    containers = define_service_containers(service_template)
    policy = perms[access_type]
    task_role = service_template.resources[TASK_ROLE_T]
    task_role.Policies.append(policy)
    for container in containers:
        if family_wide:
            extend_container_envvars(container, resource.env_vars)
        elif not family_wide and container.Name == service_name:
            extend_container_envvars(container, resource.env_vars)
            break


def apply_iam_based_resources(
    resource,
    services_families,
    services_stack,
    res_root_stack,
    perms,
    nested=False,
):
    """
    Function to assign resource to services stack

    :param resource:
    :type resource: ecs_composex.common.compose_resources.XResource
    :param dict services_families:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :raises KeyError: if the service name is not a listed service in docker-compose.
    """
    if not resource.services:
        return
    for service in resource.services:
        service_family = get_service_family_name(services_families, service["name"])
        if (
            not service_family
            or service_family not in services_stack.stack_template.resources
        ):
            raise ValueError(
                f"Service {service_family} not in the services stack",
                services_stack.stack_template.resources,
            )
        family_wide = True if service["name"] in services_families else False
        service_stack = services_stack.stack_template.resources[service_family]
        add_iam_policy_to_service_task_role(
            service_stack.stack_template,
            resource,
            perms,
            service["access"],
            NONALPHANUM.sub("", service["name"]),
            family_wide,
        )
    LOG.debug(f"{res_root_stack.title} - {nested}")
    if res_root_stack.title not in services_stack.DependsOn and not nested:
        services_stack.add_dependencies(res_root_stack.title)
