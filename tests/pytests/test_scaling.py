# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from pytest import raises

from ecs_composex.ecs.ecs_scaling import generate_scaling_out_steps


def test_steps_definition():
    """
    Function to test steps generation
    :return:
    """
    steps = generate_scaling_out_steps(
        [
            {"lower_bound": 0, "upper_bound": 20, "count": 1},
            {"lower_bound": 20, "upper_bound": 52, "count": 5},
        ],
        target=None,
    )
    assert [1, 20] == [step.MetricIntervalLowerBound for step in steps]

    with raises(ValueError):
        generate_scaling_out_steps(
            [
                {"lower_bound": 0, "upper_bound": 21, "count": 1},
                {"lower_bound": 20, "upper_bound": 52, "count": 5},
            ],
            target=None,
        )
        generate_scaling_out_steps(
            [
                {"lower_bound": 22, "upper_bound": 21, "count": 1},
                {"lower_bound": 20, "upper_bound": 52, "count": 5},
            ],
            target=None,
        )
