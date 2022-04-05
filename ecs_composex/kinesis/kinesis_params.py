# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.cfn_params import Parameter

STREAM_ID_T = "StreamId"
STREAM_ARN_T = "Arn"
STREAM_KMS_KEY_ID_T = "KmsKeyId"

STREAM_ID = Parameter(STREAM_ID_T, Type="String")
STREAM_ARN = Parameter(STREAM_ARN_T, return_value="Arn", Type="String")
STREAM_KMS_KEY_ID = Parameter(STREAM_KMS_KEY_ID_T, Type="String")
