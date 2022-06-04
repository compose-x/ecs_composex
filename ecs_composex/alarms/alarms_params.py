# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

RES_KEY = f"{X_KEY}{path.basename(path.dirname(path.abspath(__file__)))}"

LABEL = "CloudWatch Alarms"

ALARM_NAME_T = "AlarmName"
ALARM_NAME = Parameter(ALARM_NAME_T, group_label=LABEL, Type="String")

ALARM_ARN_T = "AlarmArn"
ALARM_ARN = Parameter(ALARM_ARN_T, group_label=LABEL, return_value="Arn", Type="String")
