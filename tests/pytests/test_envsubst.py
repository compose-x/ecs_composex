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

from pytest import fixture
from ecs_composex.common.envsubst import expandvars


@fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("TOTO", "toto")
    monkeypatch.setenv("TATA", "tata")


def test_envsubst(mock_env_vars):
    """
    Function to test envsubst.

    [(ENV string, expected result)]
    """
    tests = [
        ("${TOTO}", "toto"),
        ("${TOTO}$TATA$TOTO", "tototatatoto"),
        ("$TOTO $TATA", "toto tata"),
        ("$TOTO -- $TATA", "toto -- tata"),
        ("${ABCD:-Cake}", "Cake"),
        ("${TOTO:-Cake}", "toto"),
        (
            "$TOTO -- ${TATA:+SUCCESS} -- ${AWS::AccountId}",
            "toto -- SUCCESS -- ${AWS::AccountId}",
        ),
        (
            "https://s3.${AWS::Region}.${AWS::URLSuffix}",
            "https://s3.${AWS::Region}.${AWS::URLSuffix}",
        ),
    ]
    for test in tests:
        assert expandvars(test[0]) == test[1]
