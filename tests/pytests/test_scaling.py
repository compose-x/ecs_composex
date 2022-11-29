#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from pytest import raises

from ecs_composex.ecs.service_scaling.helpers import generate_scaling_out_steps


def test_steps_definition():
    """
    Function to test steps generation
    :return:
    """
    steps = generate_scaling_out_steps(
        [
            {"LowerBound": 0, "UpperBound": 20, "Count": 1},
            {"LowerBound": 20, "UpperBound": 52, "Count": 5},
        ],
        target=None,
    )
    assert [0, 20] == [step.MetricIntervalLowerBound for step in steps]

    with raises(ValueError):
        generate_scaling_out_steps(
            [
                {"LowerBound": 0, "UpperBound": 21, "Count": 1},
                {"LowerBound": 20, "UpperBound": 52, "Count": 5},
            ],
            target=None,
        )
        generate_scaling_out_steps(
            [
                {"LowerBound": 22, "UpperBound": 21, "Count": 1},
                {"LowerBound": 20, "UpperBound": 52, "Count": 5},
            ],
            target=None,
        )
