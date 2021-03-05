# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


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
