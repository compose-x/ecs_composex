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

from troposphere import Ref, AWS_NO_VALUE
from troposphere.applicationautoscaling import (
    ScalingPolicy,
    StepScalingPolicyConfiguration,
    StepAdjustment,
)

from ecs_composex.common import LOG, keyisset
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET


def generate_scaling_out_steps(steps, target):
    """

    :param list steps:
    :param tropsphere.applicationautoscaling.ScalingTarget target: The defined max in the Scalable Target
    :return:
    """
    unordered = []
    allowed_keys = ["lower_bound", "upper_bound", "count"]
    for step_def in steps:
        if not all(key in allowed_keys for key in step_def.keys()):
            raise KeyError(
                "Step definition only allows", allowed_keys, "Got", step_def.keys()
            )
        if (
            keyisset("upper_bound", step_def)
            and step_def["lower_bound"] >= step_def["upper_bound"]
        ):
            raise ValueError(
                "The lower_bound value must strictly lower than the upper bound",
                step_def,
            )
        unordered.append(step_def)
    ordered = sorted(unordered, key=lambda i: i["lower_bound"])
    if target and ordered[-1]["count"] > target.MaxCapacity:
        LOG.warn(
            f"The current maximum in your range is {target.MaxCapacity} whereas you defined {ordered[-1]['count']}"
            " for step scaling. Adjusting to step scaling max."
        )
        setattr(target, "MaxCapacity", ordered[-1]["count"])
    cfn_steps = []
    pre_upper = 0
    for step_def in ordered:
        if pre_upper and not int(step_def["lower_bound"]) >= pre_upper:
            raise ValueError(
                f"The value for lower bound is {step_def['lower_bound']},"
                f"which is higher than the previous upper_bound, {pre_upper}"
            )
        cfn_steps.append(
            StepAdjustment(
                MetricIntervalLowerBound=int(step_def["lower_bound"]),
                MetricIntervalUpperBound=int(step_def["upper_bound"])
                if keyisset("upper_bound", step_def)
                else Ref(AWS_NO_VALUE),
                ScalingAdjustment=int(step_def["count"]),
            )
        )
        pre_upper = (
            int(step_def["upper_bound"]) if keyisset("upper_bound", step_def) else None
        )
    if hasattr(cfn_steps[-1], "MetricIntervalUpperBound") and not isinstance(
        getattr(cfn_steps[-1], "MetricIntervalUpperBound"), Ref
    ):
        LOG.warn("The last upper bound shall not be set. Deleting value to comply}")
        setattr(cfn_steps[-1], "MetricIntervalUpperBound", Ref(AWS_NO_VALUE))
    return cfn_steps


def generate_alarm_scaling_out_policy(
    service_name, service_template, scaling_def, scaling_source=None
):
    """
    :param str service_name: The name of the service/family
    :param troposphere.Template service_template:
    :param dict scaling_def:
    :param str scaling_source:
    :return:
    """
    if not keyisset("steps", scaling_def):
        raise KeyError("No steps were defined in the scaling definition", scaling_def)
    steps_definition = scaling_def["steps"]
    length = 6
    if not scaling_source:
        scaling_source = "".join(
            random.choice(string.ascii_lowercase) for _ in range(length)
        )
    scalable_target = service_template.resources[SERVICE_SCALING_TARGET]
    step_adjustments = generate_scaling_out_steps(
        steps_definition, target=scalable_target
    )
    policy = ScalingPolicy(
        f"ScalingOutPolicy{scaling_source}{service_name}",
        template=service_template,
        PolicyName=f"ScalingOutPolicy{scaling_source}{service_name}",
        PolicyType="StepScaling",
        ScalingTargetId=Ref(SERVICE_SCALING_TARGET),
        ServiceNamespace="ecs",
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType="ExactCapacity",
            StepAdjustments=step_adjustments,
        ),
    )
    return policy


def reset_to_zero_policy(service_name, service_template, scaling_source=None):
    """

    :return:
    """
    length = 6
    if not scaling_source:
        scaling_source = "".join(
            random.choice(string.ascii_lowercase) for _ in range(length)
        )
    policy = ScalingPolicy(
        f"ScalingInPolicy{scaling_source}{service_name}",
        template=service_template,
        PolicyName=f"ScalingInPolicy{scaling_source}{service_name}",
        PolicyType="StepScaling",
        ScalingTargetId=Ref(SERVICE_SCALING_TARGET),
        ServiceNamespace="ecs",
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType="ExactCapacity",
            StepAdjustments=[
                StepAdjustment(
                    MetricIntervalUpperBound=0,
                    ScalingAdjustment=0,
                )
            ],
        ),
    )
    return policy
