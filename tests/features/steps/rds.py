# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from behave import then

from ecs_composex.common.stacks import ComposeXStack


@then("I should have a RDS DB")
def step_impl(context):
    """
    Function to ensure we have a RDS stack and a DB stack within
    :param context:
    :return:
    """
    template = context.root_stack.stack_template
    db_root_stack = template.resources["rds"]
    assert issubclass(type(db_root_stack), ComposeXStack)


@then("services have access to it")
def step_impl(context):
    """
    Function to ensure that the services have secret defined.
    """
