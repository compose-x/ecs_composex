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
