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

from behave import then

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs_composex import generate_full_template


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
