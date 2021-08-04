#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to apply SQS settings onto ECS Services
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap, GetAtt, Ref
from troposphere.cloudwatch import Alarm, MetricDimension

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET
from ecs_composex.ecs.ecs_scaling import (
    generate_alarm_scaling_out_policy,
    reset_to_zero_policy,
)
from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)
from ecs_composex.sqs.sqs_aws import lookup_queue_config
from ecs_composex.sqs.sqs_params import (
    MOD_KEY,
    SQS_ARN,
    SQS_KMS_KEY_T,
    SQS_NAME,
    SQS_URL,
)


def handle_service_scaling(resource, res_root_stack):
    """
    Function to define and prepare settings for scaling rules based for SQS Queues discovered through lookup

    :param ecs_composex.common.compose_resources.XResource resource:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :raises KeyError: if the service name is not a listed service in docker-compose.
    :return:
    """
    resource_attribute = SQS_NAME.title
    if not resource.lookup:
        resource_value = GetAtt(
            res_root_stack.title, f"Outputs.{resource.logical_name}{SQS_NAME.title}"
        )
    else:
        resource_value = FindInMap(MOD_KEY, resource.logical_name, resource_attribute)
    for target in resource.families_scaling:
        if SERVICE_SCALING_TARGET not in target[0].template.resources:
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
        if not resource.lookup:
            resource_parameter = Parameter(
                f"{resource.logical_name}{resource_attribute}", Type="String"
            )
            add_parameters(target[0].template, [resource_parameter])
            target[0].stack.Parameters.update(
                {resource_parameter.title: resource_value}
            )
            add_alarm_for_resource(
                resource,
                target,
                scaling_out_policy,
                scaling_in_policy,
                Ref(resource_parameter),
            )
        else:
            add_alarm_for_resource(
                resource,
                target,
                scaling_out_policy,
                scaling_in_policy,
                resource_value,
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
    Alarm(
        f"SqsScalingAlarm{resource.logical_name}To{target[0].logical_name}",
        template=target[0].template,
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
        resources[res_name]
        for res_name in resources
        if not resources[res_name].lookup and not resources[res_name].use
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
        handle_resource_to_services(
            new_res,
            services_stack,
            res_root_stack,
            settings,
            SQS_ARN,
            [SQS_URL, SQS_NAME],
        )
        handle_service_scaling(new_res, res_root_stack)
    create_sqs_mappings(resource_mappings, lookup_resources, settings)
    for lookup_res in lookup_resources:
        handle_lookup_resource(
            resource_mappings, MOD_KEY, lookup_res, SQS_ARN, [SQS_URL, SQS_NAME]
        )
        handle_service_scaling(lookup_res, None)
