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


from troposphere import Ref, Sub, GetAtt
from troposphere import AWS_REGION, AWS_NO_VALUE, AWS_PARTITION, AWS_ACCOUNT_ID
from troposphere import Parameter

from troposphere.events import Rule, Target, EcsParameters

from ecs_composex.common import (
    keypresent,
    keyisset,
    build_template,
    no_value_if_not_set,
)
from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, FARGATE_VERSION


def update_from_parameters(rule, props):
    """
    Function to update the rule props if using MacroParameters

    :param ecs_composex.events.events_stack.Rule rule:
    :param dict props:
    :return:
    """


def define_targets_from_properties(rule, props):
    """
    Function to update the rule props if using MacroParameters

    :param ecs_composex.events.events_stack.Rule rule:
    :param dict props:
    :return:
    """


def define_service_targets(rule, props, cluster_arn):
    """
    Function to define the targets for service.

    :param ecs_composex.events.events_stack.Rule rule:
    :param dict props:
    :param troposphere.Sub cluster_arn:
    :return:
    """
    for service in rule.families_targets:
        target = Target(
            EcsParameters=EcsParameters(
                NetworkConfiguration=service.ecs_service.NetworkConfiguration,
                PlatformVersion=Ref(FARGATE_VERSION),
                TaskCount=1,
                TaskDefinitionArn=Ref(service.task_definition)
            ),
            Arn=cluster_arn
        )
        props["Targets"].append(target)


def define_event_rule(rule, cluster_arn):
    """
    Function to define the EventRule properties

    :param ecs_composex.events.events_stack.Rule rule:
    :param troposphere.Sub cluster_arn:
    """
    rule_props = {
        "Description": no_value_if_not_set(rule.properties, "Description"),
        "EventBusName": no_value_if_not_set(rule.properties, "EventBusName"),
        "Name": no_value_if_not_set(rule.properties, "Name"),
        "State": no_value_if_not_set(rule.properties, "State"),
        "EventPattern": no_value_if_not_set(rule.properties, "EventPattern"),
        "ScheduleExpression": no_value_if_not_set(
            rule.properties, "ScheduleExpression"
        ),
        "Targets": []
    }
    if rule.parameters:
        update_from_parameters(rule, rule_props)
    if keyisset("Targets", rule.properties):
        define_targets_from_properties(rule, rule_props)
    if rule.services:
        define_service_targets(rule, rule_props, cluster_arn)
    rule.cfn_resource = Rule(rule.logical_name, **rule_props)


def create_events_template(settings, new_resources):
    """
    Function to create the CFN root template for Events Rules

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list new_resources:
    :return: template
    :rtype: troposphere.Template
    """
    template = build_template("Root for Events Rules in ComposeX", [CLUSTER_NAME])
    cluster_arn = Sub(
        f"arn:${{{AWS_PARTITION}}}:ecs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
        f"cluster/${{{CLUSTER_NAME.title}}}"
    )
    for resource in new_resources:
        if not resource.families_targets:
            LOG.error(
                f"The rule {resource.logical_name} does not have any families_targets defined"
            )
            continue
        define_event_rule(resource, cluster_arn)
    return template
