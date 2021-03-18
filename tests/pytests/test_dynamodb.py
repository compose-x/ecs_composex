#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

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
