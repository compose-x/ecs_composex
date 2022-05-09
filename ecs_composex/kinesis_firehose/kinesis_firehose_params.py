# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.cfn_params import Parameter

FIREHOSE_ID_T = "DeliveryStreamId"
FIREHOSE_ARN_T = "Arn"
FIREHOSE_KMS_KEY_ID_T = "KmsKeyId"

GROUP_LABEL = "Kinesis Firehose"

FIREHOSE_ID = Parameter(FIREHOSE_ID_T, group_label=GROUP_LABEL, Type="String")
FIREHOSE_ARN = Parameter(
    FIREHOSE_ARN_T, group_label=GROUP_LABEL, return_value="Arn", Type="String"
)
FIREHOSE_KMS_KEY_ID = Parameter(
    FIREHOSE_KMS_KEY_ID_T, group_label=GROUP_LABEL, Type="String"
)

FIREHOSE_CMK_MANAGER = Parameter("CmkKeyManager", Type="String")
