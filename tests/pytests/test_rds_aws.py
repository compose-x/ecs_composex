#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

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
