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

from troposphere import Ref
from troposphere.cloudwatch import Alarm, MetricDimension
from troposphere.sqs import Queue

from ecs_composex.common import keyisset, LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET
from ecs_composex.ecs.ecs_scaling import (
    generate_alarm_scaling_out_policy,
    reset_to_zero_policy,
)
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.resource_permissions import apply_iam_based_resources
from ecs_composex.resource_settings import (
    generate_resource_permissions,
    generate_export_strings,
)
from ecs_composex.sqs.sqs_params import SQS_URL, SQS_ARN, SQS_NAME
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


def handle_service_scaling(
    resource,
    services_families,
    services_stack,
    res_root_stack,
    service_def,
    nested=False,
):
    """
    Function to assign resource to services stack

    :param resource:
    :type resource: ecs_composex.common.compose_resources.XResource
    :param dict services_families:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param dict service_def: The service scaling definition
    :param bool nested: Whether this is nested stack to anohter.
    :raises KeyError: if the service name is not a listed service in docker-compose.
    """
    service_family = get_service_family_name(services_families, service_def["name"])
    if (
        not service_family
        or service_family not in services_stack.stack_template.resources
    ):
        raise ValueError(
            f"Service {service_family} not in the services stack",
            services_stack.stack_template.resources,
        )
    service_stack = services_stack.stack_template.resources[service_family]
    if SERVICE_SCALING_TARGET not in service_stack.stack_template.resources:
        LOG.warn(
            f"No Scalable target defined for {service_family}."
            " You need to define `scaling.range` in x-configs first. No scaling applied"
        )
        return
    scaling_out_policy = generate_alarm_scaling_out_policy(
        service_family,
        service_stack.stack_template,
        service_def["scaling"],
        scaling_source=resource.logical_name,
    )
    scaling_in_policy = reset_to_zero_policy(
        service_family,
        service_stack.stack_template,
        scaling_source=resource.logical_name,
    )
    Alarm(
        f"AlarmFor{resource.logical_name}To{service_family}",
        template=service_stack.stack_template,
        ActionsEnabled=True,
        AlarmActions=[Ref(scaling_out_policy)],
        AlarmDescription=f"MessagesProcessingWatchFor{resource.logical_name}To{service_family}",
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        DatapointsToAlarm=1,
        Dimensions=[
            MetricDimension(
                Name="QueueName",
                Value=generate_export_strings(resource.logical_name, SQS_NAME.title),
            ),
        ],
        EvaluationPeriods=1,
        InsufficientDataActions=[Ref(scaling_in_policy)],
        MetricName="ApproximateNumberOfMessagesVisible",
        Namespace="AWS/SQS",
        OKActions=[Ref(scaling_in_policy)],
        Period="60",
        Statistic="Sum",
        Threshold="0.0",
    )

    LOG.debug(f"{res_root_stack.title} - {nested}")
    if res_root_stack.title not in services_stack.DependsOn and not nested:
        services_stack.add_dependencies(res_root_stack.title)


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
                handle_service_scaling(
                    queue,
                    services_families,
                    services_stack,
                    res_root_stack,
                    service_def,
                )
