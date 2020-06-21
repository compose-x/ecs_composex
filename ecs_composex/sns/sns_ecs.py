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
Module to apply SNS settings onto ECS Services
"""

from ecs_composex.common import LOG, keyisset, NONALPHANUM
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.ecs.ecs_container_config import extend_container_envvars
from ecs_composex.ecs.ecs_params import TASK_ROLE_T
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.sns.sns_perms import generate_sns_permissions, generate_sns_envvars
from ecs_composex.sns.sns_templates import TOPICS_KEY


def apply_settings_to_service(
    service_template, perms, env_vars, access_type, service_name, family_wide=False
):
    """
    Function to extend task definition and task role permissions

    :param troposphere.Template service_template:
    :param dict perms:
    :param list env_vars:
    :param str access_type:
    :return:
    """
    LOG.debug(f"Adding SNS access for service {service_template}")
    containers = define_service_containers(service_template)
    policy = perms[access_type]
    task_role = service_template.resources[TASK_ROLE_T]
    task_role.Policies.append(policy)
    for container in containers:
        if family_wide:
            extend_container_envvars(container, env_vars)
        elif not family_wide and container.Name == service_name:
            LOG.debug(f"Adding env vars to {service_name} - {container.Name}")
            extend_container_envvars(container, env_vars)
            break


def sns_to_ecs(topics, services_stack, services_families, sns_root_stack, **kwargs):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    for topic_name in topics[TOPICS_KEY]:
        topic = topics[TOPICS_KEY][topic_name]
        if topic_name not in sns_root_stack.stack_template.resources:
            raise KeyError(f"SQS topic {topic_name} not a resource of the SQS stack")
        perms = generate_sns_permissions(topic_name)
        envvars = generate_sns_envvars(topic_name, topic)
        LOG.debug(topic_name)
        LOG.debug(perms)
        LOG.debug(envvars)
        LOG.debug(services_stack.stack_template.resources.keys())
        if perms and envvars and keyisset("Services", topic):
            for service in topic["Services"]:
                service_family = get_service_family_name(
                    services_families, service["name"]
                )
                family_wide = True if service["name"] in services_families else False
                if service_family not in services_stack.stack_template.resources:
                    raise KeyError(
                        f"Service {service_family} not in the services stack",
                        services_stack.stack_template.resources,
                    )
                LOG.debug(f"{service_family} detected as destination for {topic_name}")
                service_stack = services_stack.stack_template.resources[service_family]
                apply_settings_to_service(
                    service_stack.stack_template,
                    perms,
                    envvars,
                    service["access"],
                    NONALPHANUM.sub("", service["name"]),
                    family_wide,
                )
            if sns_root_stack.title not in services_stack.DependsOn:
                services_stack.DependsOn.append(sns_root_stack.title)
