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
