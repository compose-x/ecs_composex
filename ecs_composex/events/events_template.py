#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset
from troposphere.events import Rule

from ecs_composex.common import LOG
from ecs_composex.resources_import import import_record_properties


def define_event_rule(stack, rule):
    """
    Function to define the EventRule properties

    :param ecs_composex.common.stacks.ComposeXStack stack:
    :param ecs_composex.events.events_stack.Rule rule:
    """
    rule_props = import_record_properties(rule.properties, Rule)
    if not keyisset("Targets", rule_props):
        rule_props["Targets"] = []
    rule.cfn_resource = Rule(rule.logical_name, **rule_props)
    stack.stack_template.add_resource(rule.cfn_resource)


def create_events_template(stack, settings, new_resources):
    """
    Function to create the CFN root template for Events Rules

    :param ecs_composex.events.events_stack.XStack stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list new_resources:
    """
    for resource in new_resources:
        if not resource.families_targets:
            LOG.error(
                f"The rule {resource.logical_name} does not have any families_targets defined"
            )
            continue
        define_event_rule(stack, resource)
