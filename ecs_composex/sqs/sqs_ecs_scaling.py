# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to apply SQS settings onto ECS Services
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sqs_stack import Queue
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import FindInMap, GetAtt, Ref
from troposphere.cloudwatch import Alarm, MetricDimension

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
    add_update_mapping,
)
from ecs_composex.ecs.service_scaling.helpers import (
    generate_alarm_scaling_out_policy,
    reset_to_zero_policy,
)
from ecs_composex.sqs.sqs_params import SQS_NAME


def handle_service_scaling(resource: Queue, settings: ComposeXSettings = None) -> None:
    """
    Function to define and prepare settings for scaling rules based for SQS Queues discovered through lookup

    :param ecs_composex.compose.x_resources.ServicesXResource resource:
    :param ecs_composex.common. settings:
    :raises KeyError: if the service name is not a listed service in docker-compose.
    :return:
    """
    queue_id = resource.attributes_outputs[SQS_NAME]
    if resource.cfn_resource:
        queue_pointer = queue_id["ImportParameter"]
    elif resource.mappings:
        queue_pointer = queue_id["ImportValue"]
    else:
        raise AttributeError(
            resource.module.res_key, resource.name, "no mapping nor new resource"
        )
    for target in resource.families_scaling:
        if (
            not target[0].service_scaling.scalable_target
            or target[0].service_scaling.scalable_target
            not in target[0].template.resources.values()
        ):
            LOG.warning(
                f"No Scalable target defined for {target[0].name}."
                " You need to define `scaling.scaling_range` in x-configs first. No scaling applied"
            )
            return
        scaling_out_policy = generate_alarm_scaling_out_policy(
            target[0].logical_name,
            target[0].template,
            target[1],
            scaling_source=resource.logical_name,
        )
        scaling_in_policy = reset_to_zero_policy(
            target[0].logical_name,
            target[0].template,
            target[1],
            scaling_source=resource.logical_name,
        )

        if isinstance(queue_pointer, Parameter):
            add_parameters(target[0].template, [queue_pointer])
            target[0].stack.Parameters.update(
                {queue_pointer.title: queue_id["ImportValue"]}
            )
            add_alarm_for_resource(
                resource,
                target,
                scaling_out_policy,
                scaling_in_policy,
                Ref(queue_pointer),
            )
        else:
            add_update_mapping(
                target[0].template,
                resource.module.mapping_key,
                resource.module.mappings,
            )
            add_alarm_for_resource(
                resource,
                target,
                scaling_out_policy,
                scaling_in_policy,
                queue_pointer,
            )


def add_alarm_for_resource(
    resource, target, scaling_out_policy, scaling_in_policy, resource_parameter
):
    """
    Function to add the Alarm for SQS resource to the service template

    :param ecs_composex.common.compose_resources.XResource resource:
    :param tuple target:
    :param scaling_out_policy:
    :param scaling_in_policy:
    :param resource_parameter:
    :return:
    """
    alarm = Alarm(
        f"SqsScalingAlarm{resource.logical_name}To{target[0].logical_name}",
        ActionsEnabled=True,
        AlarmActions=[Ref(scaling_out_policy)],
        AlarmDescription=f"MessagesProcessingWatchFor{resource.logical_name}To{target[0].logical_name}",
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        DatapointsToAlarm=1,
        Dimensions=[
            MetricDimension(Name="QueueName", Value=resource_parameter),
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
    add_resource(target[0].template, alarm, True)
