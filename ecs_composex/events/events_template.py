#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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


from troposphere.events import (
    Rule,
)

from ecs_composex.common import LOG
from ecs_composex.common import (
    keyisset,
)
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
