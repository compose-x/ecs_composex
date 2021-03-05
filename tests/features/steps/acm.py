# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only

from behave import then
from pytest import raises

from tests.features.steps.common import *
from ecs_composex.common.stacks import ComposeXStack


@then("I should have an ACM root stack")
def step_impl(context):
    """
    Function to ensure we have an ACM stack and a DB stack within
    """
    template = context.root_stack.stack_template
    acm_root_stack = template.resources["acm"]
    assert issubclass(type(acm_root_stack), ComposeXStack)
