#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from pytest import raises, fixture
from ecs_composex.common.aws import (
    handle_multi_results,
    handle_search_results,
    validate_search_input,
)


@fixture()
def multi_matching_arns():
    return ["arn:aws:s3:::bucketabcd", "arn:aws:s3:::bucketabcd"]


@fixture()
def res_types():
    return {
        "db": {"regexp": r"(?:^arn:aws(?:-[a-z]+)?:rds:[\w-]+:[0-9]{12}:db:)([\S]+)$"},
        "cluster": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:rds:[\w-]+:[0-9]{12}:cluster:)([\S]+)$"
        },
        "secret": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:secretsmanager:[\w-]+:[0-9]{12}:secret:)([\S]+)(?:-[A-Za-z0-9]{1,6})$"
        },
    }


def test_multi_arns_exceptions(multi_matching_arns):
    with raises(LookupError):
        handle_multi_results(
            multi_matching_arns,
            "bucketxyz",
            "bucket",
            r"(?:arn:aws:s3:::)([a-z0-9-.]+$)",
        )
    with raises(LookupError):
        handle_multi_results(
            multi_matching_arns,
            "bucketabcd",
            "bucket",
            r"(?:arn:aws:s3:::)([a-z0-9-.]+$)",
        )


def test_handle_results_exceptions():
    handle_search_results(["arn:aws:s3:::sombucket-found"], None, {}, "s3")
    with raises(LookupError):
        handle_search_results([], None, {}, "s3")
    with raises(LookupError):
        handle_search_results(
            ["arn:aws:s3:::bucket1", "arn:aws:s3:::anotherone"], None, {}, "s3"
        )


def test_validate_search_input_exceptions(res_types):
    with raises(KeyError):
        validate_search_input(res_types, "abcd")
    with raises(KeyError):
        validate_search_input(res_types, 1)
