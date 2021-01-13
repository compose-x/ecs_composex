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

import boto3
from os import path
from pytest import fixture, raises
import placebo
from ecs_composex.rds.rds_aws import validate_rds_lookup, lookup_rds_resource


@fixture(autouse=True)
def valid_cluster_lookup():
    return {
        "cluster": {
            "Name": "database-1",
            "Tags": [{"dbname": "test-1"}, {"serverless": "True"}],
        },
        "secret": {
            "Name": "GHToken",
            "Tags": [{"useless": "yes"}, {"decommissioned": "true"}],
        },
    }


@fixture(autouse=True)
def unknown_lookup_property():
    return {
        "cluster": {"Name": "abcd", "Tags": [{"name": "dbtesting"}]},
        "intruder": 123,
    }


@fixture(autouse=True)
def secret_only_lookup_property():
    return {
        "secret": {"Name": "abcd", "Tags": [{"name": "dbtesting"}]},
    }


@fixture(autouse=True)
def invalid_cluster_type():
    return {"cluster": "abcd"}


@fixture(autouse=True)
def invalid_cluster_property_type():
    return {"cluster": {"Name": ["abcd"], "Tags": [{"name": "dbtesting"}]}}


@fixture(autouse=True)
def unknown_cluster_property():
    return {"cluster": {"Name": "abcd", "Tags": [{"name": "dbtesting"}], "intruder": 1}}


@fixture(autouse=True)
def valid_db_lookup():
    return {"cluster": {"Name": "abcd", "Tags": [{"name": "dbtesting"}]}}


@fixture(autouse=True)
def both_db_cluster_defined():
    return {
        "cluster": {"Name": "abcd", "Tags": [{"name": "dbtesting"}]},
        "db": {"Name": "abcd", "Tags": [{"name": "dbtesting"}]},
    }


def test_valid_rds_lookup(valid_cluster_lookup):

    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_rds_lookup")
    pill.playback()
    # pill.record()
    lookup_rds_resource(valid_cluster_lookup, session)


def test_lookup_validation(valid_db_lookup, valid_cluster_lookup):
    validate_rds_lookup("test", valid_db_lookup)
    validate_rds_lookup("test", valid_cluster_lookup)


def test_neg_lookup_validation(
    both_db_cluster_defined,
    invalid_cluster_property_type,
    invalid_cluster_type,
    unknown_cluster_property,
    unknown_lookup_property,
    secret_only_lookup_property,
):
    with raises(KeyError):
        validate_rds_lookup("test", secret_only_lookup_property)
    with raises(KeyError):
        validate_rds_lookup("test", unknown_lookup_property)
    with raises(KeyError):
        validate_rds_lookup("test", both_db_cluster_defined)
    with raises(KeyError):
        validate_rds_lookup("test", unknown_cluster_property)
    with raises(TypeError):
        validate_rds_lookup("test", 1)
    with raises(TypeError):
        validate_rds_lookup("test", invalid_cluster_property_type)
    with raises(TypeError):
        validate_rds_lookup("test", invalid_cluster_type)
