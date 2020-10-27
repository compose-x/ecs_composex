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

from ecs_composex.common import LOG
from ecs_composex.common.compose_services import extend_container_envvars
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.ecs.ecs_params import TASK_ROLE_T


def add_iam_policy_to_service_task_role_v2(
    service_template, resource, perms, access_type, services
):
    """
    Function to expand the ECS Task Role policy with the permissions for the resource
    :param troposphere.Template service_template:
    :param resource:
    :param perms:
    :param access_type:
    :param list services:
    :return:
    """
    containers = define_service_containers(service_template)
    policy = perms[access_type]
    task_role = service_template.resources[TASK_ROLE_T]
    task_role.Policies.append(policy)
    for container in containers:
        for service in services:
            if container.Name == service.name:
                LOG.debug(f"Extended env vars for {container.Name} -> {service.name}")
                extend_container_envvars(container, resource.env_vars)


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
