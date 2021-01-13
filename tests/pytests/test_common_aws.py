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
