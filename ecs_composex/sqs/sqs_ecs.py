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

from ecs_composex.common import LOG, keyisset
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET
from ecs_composex.ecs.ecs_scaling import (
    generate_alarm_scaling_out_policy,
    reset_to_zero_policy,
)
from ecs_composex.resource_settings import (
    generate_export_strings,
    handle_resource_to_services,
    handle_lookup_resource,
)
from ecs_composex.sqs.sqs_aws import lookup_queue_config
from ecs_composex.sqs.sqs_params import SQS_NAME, SQS_KMS_KEY_T


def handle_service_scaling(resource):
    """
    Function to assign resource to services stack

    :param resource:
    :type resource: ecs_composex.common.compose_resources.XResource
    :raises KeyError: if the service name is not a listed service in docker-compose.
    """
    for target in resource.families_scaling:
        if SERVICE_SCALING_TARGET not in target[0].template.resources:
            LOG.warn(
                f"No Scalable target defined for {target[0].name}."
                " You need to define `scaling.range` in x-configs first. No scaling applied"
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
        Alarm(
            f"SqsScalingAlarm{resource.logical_name}To{target[0].logical_name}",
            template=target[0].template,
            ActionsEnabled=True,
            AlarmActions=[Ref(scaling_out_policy)],
            AlarmDescription=f"MessagesProcessingWatchFor{resource.logical_name}To{target[0].logical_name}",
            ComparisonOperator="GreaterThanOrEqualToThreshold",
            DatapointsToAlarm=1,
            Dimensions=[
                MetricDimension(
                    Name="QueueName",
                    Value=generate_export_strings(
                        resource.logical_name, SQS_NAME.title
                    ),
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


def create_sqs_mappings(mapping, resources, settings):
    """
    Function to create the resource mapping for SQS Queues.

    :param dict mapping:
    :param list resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for res in resources:
        res_config = lookup_queue_config(res.lookup, settings.session)
        mapping.update({res.logical_name: res_config})
        if keyisset(SQS_KMS_KEY_T, res_config):
            LOG.info(f"Identified CMK {res_config[SQS_KMS_KEY_T]} for {res.name}")


def sqs_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    resource_mappings = {}
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
        handle_service_scaling(new_res)
    create_sqs_mappings(resource_mappings, lookup_resources, settings)
    for lookup_res in lookup_resources:
        handle_lookup_resource(resource_mappings, "sqs", lookup_res)
