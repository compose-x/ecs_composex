# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.cfn_params import Parameter

STREAM_ID_T = "StreamId"
STREAM_ARN_T = "Arn"
STREAM_KMS_KEY_ID_T = "KmsKeyId"

GROUP_LABEL = "Kinesis Data Stream"

STREAM_ID = Parameter(STREAM_ID_T, group_label=GROUP_LABEL, Type="String")
STREAM_ARN = Parameter(
    STREAM_ARN_T, group_label=GROUP_LABEL, return_value="Arn", Type="String"
)
STREAM_KMS_KEY_ID = Parameter(
    STREAM_KMS_KEY_ID_T, group_label=GROUP_LABEL, Type="String"
)
