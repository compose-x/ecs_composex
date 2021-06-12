#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

TABLE_NAME_T = "TableName"
TABLE_NAME = Parameter(TABLE_NAME_T, Type="String", AllowedPattern=r"[a-zA-Z0-9_.-]+")

TABLE_ARN_T = "Arn"
TABLE_ARN = Parameter(TABLE_ARN_T, return_value="Arn", Type="String")

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"

TABLE_SSM_PREFIX = f"/{RES_KEY}/"
