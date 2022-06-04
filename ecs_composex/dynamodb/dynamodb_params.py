# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.cfn_params import Parameter

LABEL = "DynamoDB"

TABLE_NAME_T = "TableName"
TABLE_NAME = Parameter(
    TABLE_NAME_T, group_label=LABEL, Type="String", AllowedPattern=r"[a-zA-Z0-9_.-]+"
)

TABLE_ARN_T = "Arn"
TABLE_ARN = Parameter(TABLE_ARN_T, group_label=LABEL, return_value="Arn", Type="String")
