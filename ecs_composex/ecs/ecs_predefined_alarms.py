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
Module to define well known / pre-defined alarms for ECS Services
"""

from copy import deepcopy

PREDEFINED_ALARMS_DEFINITION = {
    "HighCpuUsage": {
        "Properties": {
            "ActionsEnabled": True,
            "AlarmDescription": "HighCpuUsage",
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "MetricName": "CPUUtilization",
            "Namespace": "AWS/ECS",
            "Statistic": "Average",
        }
    },
    "ScalingOutMaxed": {
        "Properties": {
            "ActionsEnabled": True,
            "AlarmDescription": "TaskCountScalingMaxedOut",
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "MetricName": "RunningTaskCount",
            "Namespace": "ECS/ContainerInsights",
            "Statistic": "Sum",
            "Period": 60,
            "EvaluationPeriods": 1,
            "DatapointsToAlarm": 1,
        }
    },
}

PREDEFINED_SERVICE_ALARMS_DEFINITION = {
    "HighCpuUsageAndMaxScaledOut": {
        "requires_scaling": True,
        "scaling_key": "TaskCount",
        "range_key": "max",
        "Settings": {
            "CPUUtilization": 75,
            "TaskCount": 0,
            "DatapointsToAlarm": 5,
            "EvaluationPeriods": 10,
            "Period": 60,
        },
        "Primary": "HighCpuUsage",
        "Alarms": {
            "HighCpuUsage": deepcopy(PREDEFINED_ALARMS_DEFINITION["HighCpuUsage"]),
            "ScalingOutMaxed": deepcopy(
                PREDEFINED_ALARMS_DEFINITION["ScalingOutMaxed"]
            ),
            "HighCpuUsageAndMaxScaledOut": {
                "MacroParameters": {
                    "CompositeExpression": "ALARM(HighCpuUsage) AND ALARM(ScalingOutMaxed)"
                }
            },
        },
    }
}
