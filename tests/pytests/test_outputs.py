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

from pytest import raises
from troposphere import Ref

from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.outputs import validate, ComposeXOutput, get_import_value


def test_output_validation():
    """
    Function to test validation
    :return:
    """
    value = (1, 2)
    with raises(ValueError):
        validate(value)
    value = (ROOT_STACK_NAME, "Expansion", Ref(ROOT_STACK_NAME))
    validate(value)
    value = (ROOT_STACK_NAME.title, "stack", 40.1)
    with raises(TypeError):
        validate(value)
    value = (ROOT_STACK_NAME, 123, Ref(ROOT_STACK_NAME))
    with raises(TypeError):
        validate(value)
    value = (1, "toto", Ref(ROOT_STACK_NAME))
    with raises(TypeError):
        validate(value)


def test_composex_output():
    with raises(TypeError):
        ComposeXOutput("object", values=((1, 2, 3), (1, 2, 3)))
    with raises(TypeError):
        ComposeXOutput(ROOT_STACK_NAME, values=[[1, 2, 3], [4, 5, 6]])
    ComposeXOutput(ROOT_STACK_NAME, [(ROOT_STACK_NAME, "stack", Ref(ROOT_STACK_NAME))])
    ComposeXOutput(
        None, [(ROOT_STACK_NAME, "stack", Ref(ROOT_STACK_NAME))], duplicate_attr=True
    )
    with raises(TypeError):
        ComposeXOutput(
            123, [(ROOT_STACK_NAME, "stack", Ref(ROOT_STACK_NAME))], duplicate_attr=True
        )


def test_import_value():
    get_import_value("toto", "Arn", delimiter=123)
