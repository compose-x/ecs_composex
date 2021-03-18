#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from tests.features.steps.common import *
from behave import then
from pytest import raises


from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.sqs.sqs_stack import XStack
from ecs_composex.common.stacks import process_stacks


@given("I process and render the queues")
def step_impl(context):
    context.root_stack = XStack("sqs", context.settings)
    process_stacks(context.root_stack, context.settings)


@then("I should have SQS queues")
def step_impl(context):
    """
    Function to ensure we have a RDS stack and a DB stack within
    :param context:
    :return:
    """
    template = context.root_stack.stack_template
    sqs_root_stack = template.resources["sqs"]
    services_root_stack = template.resources["services"]
    assert issubclass(type(sqs_root_stack), ComposeXStack)
    assert issubclass(type(services_root_stack), ComposeXStack)
    context.svc_stack = services_root_stack
    context.sqs_stack = sqs_root_stack


@given("I want to deploy only SQS")
def step_impl(context):
    context.resource_type = XStack


@then("services have access to the queues")
def step_impl(context):
    """
    Function to ensure that the services have secret defined.
    """
