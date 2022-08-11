# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

"""
Module to test ecs_composex generic oneliner raise functions.
"""

from os import path

import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import boto3
import placebo
from botocore.exceptions import ClientError
from pytest import fixture, raises

from ecs_composex.common.settings import ComposeXSettings


@fixture(autouse=False)
def env_setup(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "ANCD")


def get_basic_content():
    here = path.abspath(path.dirname(__file__))
    with open(f"{here}/../../use-cases/blog.yml") as composex_fd:
        return yaml.load(composex_fd.read(), Loader=Loader)


def get_secrets_content():
    here = path.abspath(path.dirname(__file__))
    with open(f"{here}/../../use-cases/blog.features.yml") as composex_fd:
        return yaml.load(composex_fd.read(), Loader=Loader)


def test_iam_role_arn():
    case_path = "settings/role_arn"
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/{case_path}")
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
