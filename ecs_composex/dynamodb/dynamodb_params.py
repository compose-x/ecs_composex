# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from os import path
from ecs_composex.ecs_composex import X_KEY
from ecs_composex.common.cfn_params import Parameter

TABLE_NAME_T = "TableName"
TABLE_NAME = Parameter(TABLE_NAME_T, Type="String", AllowedPattern=r"[a-zA-Z0-9_.-]+")

TABLE_ARN_T = "Arn"
TABLE_ARN = Parameter(TABLE_ARN_T, return_value="Arn", Type="String")

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"

TABLE_SSM_PREFIX = f"/{RES_KEY}/"
