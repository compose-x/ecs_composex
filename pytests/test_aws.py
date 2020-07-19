#  -*- coding: utf-8 -*-
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

from os import path
import pytest
import placebo
import boto3
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.vpc.vpc_params import VPC_ID_T


@pytest.fixture
def here():
    return path.abspath(path.dirname(__file__))


def test_vpc_import_from_tags(here):
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_vpc")
    pill.playback()
    settings = ComposeXSettings(
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.input_file_arg: f"{here}/../use-cases/vpc/vpc_from_tags.yml",
            ComposeXSettings.no_upload_arg: True,
            ComposeXSettings.format_arg: "yaml",
        },
    )
    assert hasattr(settings, VPC_ID_T) and getattr(settings, VPC_ID_T) is not None


def test_vpc_import_from_id(here):
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_vpc")
    pill.playback()
    settings = ComposeXSettings(
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.input_file_arg: f"{here}/../use-cases/vpc/vpc_from_id.yml",
            ComposeXSettings.no_upload_arg: True,
            ComposeXSettings.format_arg: "yaml",
        },
    )
    assert hasattr(settings, VPC_ID_T) and getattr(settings, VPC_ID_T) is not None


def test_vpc_import_from_arn(here):
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_vpc")
    pill.playback()
    settings = ComposeXSettings(
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.input_file_arg: f"{here}/../use-cases/vpc/vpc_from_arn.yml",
            ComposeXSettings.no_upload_arg: True,
            ComposeXSettings.format_arg: "yaml",
        },
    )
    assert hasattr(settings, VPC_ID_T) and getattr(settings, VPC_ID_T) is not None
