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

from ecs_composex.common import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET
from ecs_composex.ecs.ecs_scaling import (
    generate_alarm_scaling_out_policy,
    reset_to_zero_policy,
)
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.resource_permissions import add_iam_policy_to_service_task_role_v2
from ecs_composex.resource_settings import (
    generate_resource_permissions,
    generate_export_strings,
)
from ecs_composex.sqs.sqs_params import SQS_URL, SQS_ARN, SQS_NAME
from ecs_composex.sqs.sqs_perms import ACCESS_TYPES


def map_service_perms_to_resource(resource, family, services, access):
    """
    Function to
    :param resource:
    :param family:
    :param services:
    :param str access:
    :return:
    """
    res_perms = generate_resource_permissions(
        f"AccessTo{resource.logical_name}", ACCESS_TYPES, None, SQS_ARN
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
    resource.generate_resource_envvars(attribute=SQS_URL)
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
                resource, target[0], select_services, target[3]
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


def handle_service_scaling(
    resource,
    services_stack,
    res_root_stack,
    service_def,
    nested=False,
):
    """
    Function to assign resource to services stack

    :param resource:
    :type resource: ecs_composex.common.compose_resources.XResource
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param dict service_def: The service scaling definition
    :param bool nested: Whether this is nested stack to anohter.
    :raises KeyError: if the service name is not a listed service in docker-compose.
    """
    service_family = get_service_family_name(service_def["name"])
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
        service_def["scaling"],
        scaling_source=resource.logical_name,
    )
    Alarm(
        f"SqsScalingAlarm{resource.logical_name}To{service_family}",
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
        TreatMissingData="notBreaching",
        Threshold=float(
            scaling_out_policy.StepScalingPolicyConfiguration.StepAdjustments[
                0
            ].MetricIntervalLowerBound
        ),
    )
    LOG.debug(f"{res_root_stack.title} - {nested}")
    if res_root_stack.title not in services_stack.DependsOn and not nested:
        services_stack.add_dependencies(res_root_stack.title)


def sqs_to_ecs(resources, services_stack, res_root_stack, settings, **kwargs):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].lookup and not resources[res_name].properties
    ]
    if new_resources and res_root_stack.title not in services_stack.DependsOn:
        services_stack.DependsOn.append(res_root_stack.title)
        LOG.info(f"Added dependency between services and {res_root_stack.title}")
    for new_res in new_resources:
        handle_resource_to_services(new_res, services_stack, res_root_stack, settings)

    # for queue_name in queues:
    #     queue = queues[queue_name]
    #     for service_def in queue.services:
    #         if keyisset("scaling", service_def):
    #             handle_service_scaling(
    #                 queue,
    #                 services_stack,
    #                 res_root_stack,
    #                 service_def,
    #             )
