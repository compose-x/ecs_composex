# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


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
