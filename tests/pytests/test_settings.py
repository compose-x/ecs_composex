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

"""
Module to test ecs_composex generic oneliner raise functions.
"""

import placebo
import boto3
from os import path
from copy import deepcopy
from pytest import raises, fixture
from botocore.exceptions import ClientError

from troposphere import ImportValue
from ecs_composex.resource_settings import generate_export_strings
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common import load_composex_file


@fixture(autouse=False)
def env_setup(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "ANCD")


def test_export_attribute():
    """
    Function to verify the raise for invalid attribute
    """
    export_string = generate_export_strings("toto", "Arn")
    assert isinstance(export_string, ImportValue)

    with raises(TypeError):
        generate_export_strings("toto", 123)


def get_basic_content():
    here = path.abspath(path.dirname(__file__))
    content = load_composex_file(f"{here}/../../use-cases/blog.yml")
    return deepcopy(content)


def get_secrets_content():
    here = path.abspath(path.dirname(__file__))
    content = load_composex_file(f"{here}/../../use-cases/blog.features.yml")
    return deepcopy(content)


def test_iam_role_arn():
    case_path = "settings/role_arn"
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/{case_path}")
    # pill.record()
    pill.playback()

    settings = ComposeXSettings(
        content=get_basic_content(),
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.input_file_arg: path.abspath(
                f"{here}/../../uses-cases/blog.yml"
            ),
            ComposeXSettings.format_arg: "yaml",
            ComposeXSettings.arn_arg: "arn:aws:iam::012345678912:role/testx",
        },
    )
    print(settings.secrets_mappings)
    with raises(ValueError):
        ComposeXSettings(
            content=get_basic_content(),
            session=session,
            **{
                ComposeXSettings.name_arg: "test",
                ComposeXSettings.command_arg: ComposeXSettings.render_arg,
                ComposeXSettings.input_file_arg: path.abspath(
                    f"{here}/../../uses-cases/blog.yml"
                ),
                ComposeXSettings.format_arg: "yaml",
                ComposeXSettings.arn_arg: "arn:aws:iam::012345678912:roleX/testx",
            },
        )
    with raises(ClientError):
        ComposeXSettings(
            content=get_basic_content(),
            session=session,
            **{
                ComposeXSettings.name_arg: "test",
                ComposeXSettings.command_arg: ComposeXSettings.render_arg,
                ComposeXSettings.input_file_arg: path.abspath(
                    f"{here}/../../uses-cases/blog.yml"
                ),
                ComposeXSettings.format_arg: "yaml",
                ComposeXSettings.arn_arg: "arn:aws:iam::012345678912:role/test",
            },
        )


def test_secrets_import():
    """
    Function to test secrets import
    """
    case_path = "settings/secrets"
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/{case_path}")
    # pill.record()
    pill.playback()

    settings = ComposeXSettings(
        content=get_secrets_content(),
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.input_file_arg: path.abspath(
                f"{here}/../../uses-cases/blog.features.yml"
            ),
            ComposeXSettings.format_arg: "yaml",
        },
    )
