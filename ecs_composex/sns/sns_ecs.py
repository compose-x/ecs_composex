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

from ecs_composex.common import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resource_permissions import add_iam_policy_to_service_task_role_v2
from ecs_composex.resource_settings import (
    generate_resource_permissions,
)
from ecs_composex.sns.sns_params import TOPIC_ARN_T
from ecs_composex.sns.sns_perms import ACCESS_TYPES
from ecs_composex.sns.sns_stack import Topic as XTopic


def map_service_perms_to_resource(resource, family, services, access, arn_attribute):
    """
    Function to
    :param resource:
    :param family:
    :param services:
    :param str access:
    :param arn_attribute:
    :return:
    """
    res_perms = generate_resource_permissions(
        f"AccessTo{resource.logical_name}", ACCESS_TYPES, None, arn=arn_attribute
    )
    add_iam_policy_to_service_task_role_v2(
        family.template,
        resource,
        res_perms,
        access,
        services,
    )


def assign_new_queue_to_service(resource, nested=False):
    """
    Function to assign the new resource to the service/family using it.

    :param ecs_composex.common.compose_resources.XResource resource:
    :param bool nested: Whether this call if for a nested resource or not.

    :return:
    """
    select_services = []
    resource.generate_resource_envvars(attribute=TOPIC_ARN_T)
    for target in resource.families_targets:
        if not target[1] and target[2]:
            LOG.debug(
                f"Resource {resource.name} only applies to {target[2]} in family {target[0].name}"
            )
            select_services = target[2]
        elif target[1]:
            LOG.debug(f"Resource {resource.name} applies to family {target[0].name}")
            select_services = target[0].services
        if select_services:
            map_service_perms_to_resource(
                resource, target[0], select_services, target[3], TOPIC_ARN_T
            )


def handle_resource_to_services(
    xresource,
    services_stack,
    res_root_stack,
    settings,
    nested=False,
):
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_resource_to_services(
                s_resources[resource_name],
                services_stack,
                res_root_stack,
                settings,
                nested=True,
            )
    assign_new_queue_to_service(xresource, nested)


def sns_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    new_resources = [
        resources[XTopic.keyword][resource_name]
        for resource_name in resources[XTopic.keyword]
        if not resources[XTopic.keyword][resource_name].lookup
    ]
    lookup_resources = [
        resources[XTopic.keyword][resource_name]
        for resource_name in resources[XTopic.keyword]
        if resources[XTopic.keyword][resource_name].lookup
    ]
    if new_resources and res_root_stack.title not in services_stack.DependsOn:
        services_stack.DependsOn.append(res_root_stack.title)
        LOG.info(f"Added dependency between services and {res_root_stack.title}")
    for new_res in new_resources:
        handle_resource_to_services(
            new_res, services_stack, res_root_stack, settings, False
        )
