#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

"""
Module to help generate target scaling policies for given alarms.
"""

import random
import string

from troposphere import Ref, Sub, AWS_NO_VALUE, AWS_ACCOUNT_ID
from troposphere.cloudwatch import Alarm
from troposphere.applicationautoscaling import (
    ScalingPolicy,
    StepScalingPolicyConfiguration,
    StepAdjustment,
)

from ecs_composex.common import LOG, keyisset
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET


def generate_scaling_out_steps(steps):
    """

    :param steps:
    :return:
    """
    unordered = []
    allowed_keys = ["lower_bound", "upper_bound", "count"]
    for step_def in steps:
        if not all(key in allowed_keys for key in step_def.keys()):
            raise KeyError(
                "Step definition only allows", allowed_keys, "Got", step_def.keys()
            )
        if step_def["lower_bound"] >= step_def["upper_bound"]:
            raise ValueError(
                "The lower_bound value must strictly lower than the upper bound",
                step_def,
            )
        unordered.append(step_def)
    ordered = sorted(unordered, key=lambda i: i["lower_bound"])
    cfn_steps = []
    pre_upper = 0
    for step_def in ordered:
        if not int(step_def["lower_bound"]) >= pre_upper:
            raise ValueError(
                f"The value for lower bound is {step_def['lower_bound']},"
                f"which is higher than the previous upper_bound, {pre_upper}"
            )
        cfn_steps.append(
            StepAdjustment(
                MetricIntervalLowerBound=int(step_def["lower_bound"]),
                MetricIntervalUpperBound=int(step_def["upper_bound"]),
                ScalingAdjustment=int(step_def["count"]),
            )
        )
        pre_upper = int(step_def["upper_bound"])
    return cfn_steps


def generate_alarm_scaling_out_policy(
    service, service_template, steps_definition, scaling_source=None
):
    """

    :param ecs_composex.common.compose_resources.Service service:
    :param troposphere.Template service_template:
    :param list steps_definition:
    :param str scaling_source:
    :return:
    """
    length = 6
    if not scaling_source:
        scaling_source = "".join(
            random.choice(string.ascii_lowercase) for count in range(length)
        )
    policy = ScalingPolicy(
        f"ScalingOutPolicy${scaling_source}{service.logical_name}",
        template=service_template,
        PolicyName=f"ScalingOutPolicy${scaling_source}{service.logical_name}",
        PolicyType="StepScaling",
        ScalingTargetId=Ref(SERVICE_SCALING_TARGET),
        ServiceNamespace="ecs",
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType="ExactCapacity",
            StepAdjustments=generate_scaling_out_steps(steps_definition),
        ),
    )
    return policy


def generate_alarm_scaling_in_policy():
    """

    :return:
    """
    policy = ScalingPolicy(f"ScalingInPolicy")


if __name__ == "__main__":
    steps = generate_scaling_out_steps(
        [
            {"lower_bound": 0, "upper_bound": 20, "count": 1},
            {"lower_bound": 20, "upper_bound": 52, "count": 5},
        ]
    )
    for step in steps:
        print(step, step.MetricIntervalLowerBound)
