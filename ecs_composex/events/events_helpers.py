#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.common.settings import ComposeXSettings
    from .events_stack import Rule

from compose_x_common.compose_x_common import keyisset
from troposphere import NoValue
from troposphere.events import Rule as CfnRule

from ecs_composex.common.logging import LOG
from ecs_composex.resources_import import import_record_properties


def define_event_rule(stack: ComposeXStack, rule: Rule) -> None:
    """
    Function to define the EventRule properties

    :param ecs_composex.common.stacks.ComposeXStack stack:
    :param ecs_composex.events.events_stack.Rule rule:
    """
    rule_props = import_record_properties(rule.properties, CfnRule)
    if not keyisset("Targets", rule_props):
        rule_props["Targets"] = []
    if not keyisset("Name", rule_props) or rule_props["Name"] == "":
        rule_props["Name"] = NoValue
    rule.cfn_resource = CfnRule(rule.logical_name, **rule_props)
    stack.stack_template.add_resource(rule.cfn_resource)


def create_events_template(
    stack: ComposeXStack, settings: ComposeXSettings, new_resources: list[Rule]
) -> None:
    """
    Function to create the CFN root template for Events Rules

    :param ecs_composex.events.events_stack.XStack stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list[Rule] new_resources:
    """
    for resource in new_resources:
        if not resource.families_targets:
            LOG.error(
                f"The rule {resource.logical_name} does not have any families_targets defined"
            )
            continue
        define_event_rule(stack, resource)
