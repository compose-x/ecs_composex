# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from os import path
from ecs_composex.ecs_composex import X_KEY
from ecs_composex.common.cfn_params import Parameter


MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"

STREAM_ID_T = "StreamId"
STREAM_ARN_T = "Arn"
STREAM_KMS_KEY_ID_T = "KmsKeyId"

STREAM_ID = Parameter(STREAM_ID_T, Type="String")
STREAM_ARN = Parameter(STREAM_ARN_T, return_value="Arn", Type="String")
STREAM_KMS_KEY_ID = Parameter(STREAM_KMS_KEY_ID_T, Type="String")
