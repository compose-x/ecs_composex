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
