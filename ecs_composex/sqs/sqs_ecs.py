# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to apply SQS settings onto ECS Services
"""

from troposphere.sqs import Queue

from ecs_composex.common import keyisset, LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resource_permissions import apply_iam_based_resources
from ecs_composex.resource_settings import (
    generate_resource_permissions,
)
from ecs_composex.sqs.sqs_params import SQS_URL, SQS_ARN
from ecs_composex.sqs.sqs_perms import ACCESS_TYPES


def handle_new_queues(
    xresources,
    services_families,
    services_stack,
    res_root_stack,
    l_queues,
    nested=False,
):
    queues_r = []
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if isinstance(s_resources[resource_name], Queue):
            queues_r.append(s_resources[resource_name].title)
        elif issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_queues(
                xresources,
                services_families,
                services_stack,
                s_resources[resource_name],
                l_queues,
                nested=True,
            )

    for queue_name in xresources:
        if queue_name in queues_r:
            queue = xresources[queue_name]
            queue.generate_resource_envvars(SQS_URL)
            perms = generate_resource_permissions(
                queue.logical_name, ACCESS_TYPES, SQS_ARN.title
            )
            apply_iam_based_resources(
                queue,
                services_families,
                services_stack,
                res_root_stack,
                perms,
                nested,
            )
            del l_queues[queue_name]


def sqs_to_ecs(
    queues, services_stack, services_families, res_root_stack, settings, **kwargs
):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    l_queues = queues.copy()
    handle_new_queues(
        queues, services_families, services_stack, res_root_stack, l_queues
    )

    for queue_name in queues:
        queue = queues[queue_name]
        for service_def in queue.services:
            if keyisset("scaling", service_def):
                handle_service_scaling(service_def, queue, res_root_stack)
