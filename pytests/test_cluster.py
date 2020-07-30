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
import boto3
import placebo
from troposphere import Template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.ecs.ecs_cluster import add_ecs_cluster


@pytest.fixture
def existing_cluster():
    return {"x-cluster": {"Lookup": "test"}}


@pytest.fixture
def nonexisting_cluster():
    return {"x-cluster": {"Lookup": "test2"}}


def test_lookup(existing_cluster, nonexisting_cluster):
    """
    Function to test the dynamodb table lookup
    """
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_ecs")
    pill.playback()
    template = Template()
    stack = ComposeXStack("test", stack_template=template)
    settings = ComposeXSettings(content=existing_cluster, session=session, Name="abcd")
    cluster = add_ecs_cluster(settings, stack)
    assert cluster is False

    template = Template()
    stack = ComposeXStack("test", stack_template=template)
    settings = ComposeXSettings(
        content=nonexisting_cluster, session=session, Name="abcd"
    )
    cluster = add_ecs_cluster(settings, stack)
    assert cluster is True
