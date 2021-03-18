#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

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
