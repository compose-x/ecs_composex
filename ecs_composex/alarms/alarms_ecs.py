﻿#  -*- coding: utf-8 -*-
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


from troposphere import Output
from troposphere import Ref, GetAtt
from troposphere.cloudwatch import Alarm as CWAlarm, CompositeAlarm, MetricDimension

from ecs_composex.common import LOG
from ecs_composex.common import keyisset, add_parameters, add_outputs
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET
from ecs_composex.ecs.ecs_scaling import (
    generate_alarm_scaling_out_policy,
    reset_to_zero_policy,
)
from ecs_composex.ecs.ecs_params import SERVICE_T, CLUSTER_NAME
from ecs_composex.sns.sns_params import (
    RES_KEY as SNS_KEY,
    TOPIC_ARN_RE,
    TOPIC_ARN,
)
from ecs_composex.sns.sns_stack import Topic
from ecs_composex.alarms.alarms_stack import create_alarms, Alarm


def get_alarm_actions(alarm):
    """
    Function to get the alarm actions

    :param alarm:
    :return: the okay and alarm actions
    :rtype: tuple
    """
    if hasattr(alarm.cfn_resource, "OKActions"):
        okay_actions = getattr(alarm.cfn_resource, "OKActions")
    else:
        okay_actions = []
        setattr(alarm.cfn_resource, "OKActions", okay_actions)
    if hasattr(alarm.cfn_resource, "AlarmActions"):
        alarm_actions = getattr(alarm.cfn_resource, "AlarmActions")
    else:
        alarm_actions = []
        setattr(alarm.cfn_resource, "AlarmActions", alarm_actions)
    return okay_actions, alarm_actions


def handle_services_alarm_access(alarm):
    """
    Function to grant describe access onto the alarm

    :param alarm:
    :return:
    """


def add_service_actions(
    alarm, alarms_stack, target, scaling_in_policy, scaling_out_policy
):
    """
    Function to update the alarm properties with OKActions and AlarmActions

    :param ecs_composex.alarms.alarms_stack.Alarm alarm:
    :param ecs_composex.common.stacks.ComposeXStack alarms_stack:
    :param tuple target:
    :param scaling_in_policy:
    :param scaling_out_policy:
    """
    setattr(
        alarm,
        "Threshold",
        float(
            scaling_out_policy.StepScalingPolicyConfiguration.StepAdjustments[
                0
            ].MetricIntervalLowerBound
        ),
    )
    if not alarm.cfn_resource:
        raise AttributeError(f"Alarm {alarm.logical_name} has no CFN object associated")
    service_scaling_in_policy_param = Parameter(
        f"{target[0].logical_name}ScaleInPolicy", Type="String"
    )
    service_scaling_out_policy_param = Parameter(
        f"{target[0].logical_name}ScaleOutPolicy", Type="String"
    )
    add_parameters(
        alarms_stack.stack_template,
        [service_scaling_in_policy_param, service_scaling_out_policy_param],
    )
    add_outputs(
        target[0].template,
        [
            Output(
                f"{target[0].logical_name}ScaleInPolicy",
                Value=Ref(scaling_in_policy),
            ),
            Output(
                f"{target[0].logical_name}ScaleOutPolicy",
                Value=Ref(scaling_out_policy),
            ),
        ],
    )
    alarms_stack.Parameters.update(
        {
            service_scaling_in_policy_param.title: GetAtt(
                target[0].logical_name,
                f"Outputs.{target[0].logical_name}ScaleInPolicy",
            ),
            service_scaling_out_policy_param.title: GetAtt(
                target[0].logical_name,
                f"Outputs.{target[0].logical_name}ScaleOutPolicy",
            ),
        }
    )
    actions = get_alarm_actions(alarm)
    actions[0].append(Ref(service_scaling_in_policy_param))
    actions[1].append(Ref(service_scaling_out_policy_param))


def handle_service_scaling(alarm, alarms_stack):
    """
    Function to create the scaling steps for defined services

    :param ecs_composex.alarms.alarms_stack.Alarm alarm:
    :param ecs_composex.common.stacks.ComposeXStack alarms_stack:
    """
    for target in alarm.families_scaling:
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
            scaling_source=alarm.logical_name,
        )
        scaling_in_policy = reset_to_zero_policy(
            target[0].logical_name,
            target[0].template,
            target[1],
            scaling_source=alarm.logical_name,
        )
        add_service_actions(
            alarm, alarms_stack, target, scaling_in_policy, scaling_out_policy
        )


def map_topic_to_action(alarm, notify_on, topic_identifier):
    """
    Function to map the topic to specific actions

    :param alarm: alarm props for alarms
    :param str notify_on:
    :param topic_identifier:
    :return:
    """
    actions = get_alarm_actions(alarm)
    if notify_on == "all":
        actions[0].append(topic_identifier)
        actions[1].append(topic_identifier)
    elif notify_on == "alarm":
        actions[1].append(topic_identifier)
    elif notify_on == "okay":
        actions[0].append(topic_identifier)


def handle_notify_on(topic_def):
    """
    Function to validate parameter NotifyOn

    :param dict topic_def:
    :return:
    """
    valid_values = ["all", "okay", "alarm"]
    notify_on = "alarm"
    if not keyisset("NotifyOn", topic_def):
        LOG.warning("NotifyOn was not set for topic. Will default to AlarmActions")
    else:
        if not isinstance(topic_def["NotifyOn"], str):
            raise TypeError("NotifyOn must be a string")
        notify_on = topic_def["NotifyOn"].lower()
        if notify_on not in valid_values:
            raise ValueError(
                "The value for NotifyOn",
                notify_on,
                "Is not valid. Expected one of",
                valid_values,
            )
    return notify_on


def handle_compose_topics(alarm, alarms_stack, settings, topic_def, notify_on):
    """
    Function to handle x-alarms to x-sns topics

    :param ecs_composex.alarms.alarms_stack.Alarm alarm:
    :param ecs_composex.common.stacks.ComposeXStack alarms_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param dict topic_def:
    :param str notify_on:
    :return:
    """
    try:
        topic = settings.compose_content[SNS_KEY][Topic.keyword][topic_def[SNS_KEY]]
    except KeyError:
        LOG.error(f"No topic {topic_def[SNS_KEY]} found in {SNS_KEY}.{Topic.keyword}")
        raise
    if not topic.attributes_outputs:
        topic.init_outputs()
        topic.generate_outputs()
    topic_arn = topic.attributes_outputs[TOPIC_ARN]
    if topic.cfn_resource:
        add_parameters(alarms_stack.stack_template, [topic_arn["ImportParameter"]])
        alarms_stack.Parameters.update({topic_arn["Name"]: topic_arn["ImportValue"]})
        map_topic_to_action(alarm, notify_on, Ref(topic_arn["ImportParameter"]))
    else:
        if keyisset(SNS_KEY, settings.mappings) and keyisset(
            topic.logical_name, settings.mappings[SNS_KEY]
        ):
            alarms_stack.stack_template.add_mapping(
                topic.module_name, settings.mappings[SNS_KEY]
            )
            map_topic_to_action(alarm, notify_on, topic_arn["ImportValue"])


def handle_alarm_topics(alarm, alarms_stack, settings):
    """
    Function to add the topics actions for defined topics

    :param ecs_composex.alarms.alarms_stack.Alarm alarm:
    :param ecs_composex.common.stacks.ComposeXStack alarms_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """

    for topic in alarm.topics:
        notify_on = handle_notify_on(topic)
        if keyisset("TopicArn", topic):
            if not TOPIC_ARN_RE.match(topic["TopicArn"]):
                raise ValueError("Invalid ARN for topic", topic["TopicArn"])
            map_topic_to_action(alarm, notify_on, topic["TopicArn"])
        elif keyisset(SNS_KEY, topic):
            if not keyisset(SNS_KEY, settings.compose_content) or (
                keyisset(SNS_KEY, settings.compose_content)
                and not keyisset(
                    topic[SNS_KEY], settings.compose_content[SNS_KEY][Topic.keyword]
                )
            ):
                raise KeyError(
                    f"There is no topic {topic[SNS_KEY]} defined in {SNS_KEY}"
                )
            handle_compose_topics(alarm, alarms_stack, settings, topic, notify_on)


def alarms_to_ecs(resources, services_stack, res_root_stack, settings):
    new_resources = [
        resource
        for resource in resources.values()
        if not resource.lookup and not resource.use
    ]
    for alarm in new_resources:
        if alarm.in_composite:
            continue
        handle_service_scaling(alarm, res_root_stack)
        if alarm.topics:
            handle_alarm_topics(alarm, res_root_stack, settings)


def update_alarm_threshold(alarm_properties, settings):
    """
    Function to update the threshold based on the defined settings

    :param alarm_properties:
    :param settings:
    :return:
    """
    if alarm_properties["MetricName"] in settings and keyisset(
        alarm_properties["MetricName"], settings
    ):
        alarm_properties["Threshold"] = float(settings[alarm_properties["MetricName"]])


def update_definition_from_settings(alarm_definition, settings):
    """
    Function to update the alarm definition with the global settings

    :param dict alarm_definition:
    :param dict settings:
    :return:
    """
    alarm_definition["Properties"].update(
        {
            "DatapointsToAlarm": settings["DatapointsToAlarm"],
            "EvaluationPeriods": settings["EvaluationPeriods"],
            "Period": settings["Period"],
        }
    )


def set_services_alarms(settings):
    """
    Function to create and assign alarms to services

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for family in settings.families.values():
        if not family.predefined_alarms:
            continue
        family_alarms = []
        for name, definition in family.predefined_alarms.items():
            primary_name = definition["Primary"]
            primary = definition["Alarms"][primary_name]
            update_definition_from_settings(primary, definition["Settings"])
            for alarm_name, alarm_definition in definition["Alarms"].items():
                if keyisset("Topics", definition):
                    alarm_definition["Topics"] = definition["Topics"]
                if keyisset("Properties", alarm_definition) and keyisset(
                    "MetricName", alarm_definition["Properties"]
                ):
                    update_alarm_threshold(
                        alarm_definition["Properties"], definition["Settings"]
                    )
                the_alarm = Alarm(
                    alarm_name, alarm_definition, family.logical_name, settings
                )
                family_alarms.append(the_alarm)
        create_alarms(family.template, settings, family_alarms)
        for alarm in family_alarms:
            dimensions = [
                MetricDimension(**{"Name": "ClusterName", "Value": Ref(CLUSTER_NAME)}),
                MetricDimension(
                    **{
                        "Name": "ServiceName",
                        "Value": GetAtt(family.ecs_service.ecs_service, "Name"),
                    }
                ),
            ]
            if isinstance(alarm.cfn_resource, CWAlarm):
                setattr(alarm.cfn_resource, "Dimensions", dimensions)
            if issubclass(type(alarm.cfn_resource), CompositeAlarm):
                handle_alarm_topics(alarm, family.stack, settings)
