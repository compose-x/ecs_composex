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

from os import path
import pytest
import boto3
import placebo
from ecs_composex.dynamodb.dynamodb_aws import lookup_dynamodb_config


@pytest.fixture
def existing_table_tags():
    return {"Tags": [{"createdbycomposex": "False"}, {"name": "tableC"}]}


@pytest.fixture
def overlaping_existing_table_tags():
    return {"Tags": [{"name": "tableC"}]}


def test_lookup(existing_table_tags):
    """
    Function to test the dynamodb table lookup

    :param existing_table_tags:
    :return:
    """
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_dynamodb")
    pill.playback()
    lookup_dynamodb_config(existing_table_tags, session)


def test_lookup_multiple(overlaping_existing_table_tags):
    """
    Function to test the dynamodb table lookup

    :param overlaping_existing_table_tags:
    :return:
    """
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_dynamodb")
    pill.playback()
    with pytest.raises(LookupError):
        lookup_dynamodb_config(overlaping_existing_table_tags, session)
        lookup_dynamodb_config(overlaping_existing_table_tags, session)
