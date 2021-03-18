#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from ecs_composex.secrets.compose_secrets import define_env_var_name


def test_normal_secrets():
    """
    Function to test valid secrets definitions
    :return:
    """
    assert "example" == define_env_var_name({"SecretKey": "example"})
    assert "EXAMPLE" == define_env_var_name(
        {"SecretKey": "example", "VarName": "EXAMPLE"}
    )
    assert "SOME_PROPERTY" == define_env_var_name(
        {"SecretKey": "some.property", "Transform": "java_properties"}
    )
    assert "SOME.PROPERTY" == define_env_var_name(
        {"SecretKey": "some.property", "Transform": "capitalize"}
    )
    assert "Some.Property" == define_env_var_name(
        {"SecretKey": "some.property", "Transform": "title"}
    )
    assert "EXAMPLE" == define_env_var_name(
        {
            "SecretKey": "some.property",
            "VarName": "EXAMPLE",
            "Transform": "java_properties",
        }
    )
