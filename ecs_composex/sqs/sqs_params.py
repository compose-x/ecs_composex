# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>


from ecs_composex.common.cfn_params import Parameter

TAGGING_API_ID = "sqs"

SQS_SETTINGS = "SQS Settings"

SQS_URL_T = "Url"
SQS_URL = Parameter(SQS_URL_T, group_label=SQS_SETTINGS, Type="String")

SQS_ARN_T = "Arn"
SQS_ARN = Parameter(
    SQS_ARN_T, group_label=SQS_SETTINGS, return_value="Arn", Type="String"
)

SQS_NAME_T = "QueueName"
SQS_NAME = Parameter(
    SQS_NAME_T, group_label=SQS_SETTINGS, return_value="QueueName", Type="String"
)

DLQ_NAME_T = "DeadLetterQueueName"
DLQ_NAME = Parameter(DLQ_NAME_T, group_label=SQS_SETTINGS, Type="String")

DLQ_ARN_T = "DeadLetterQueueArn"
DLQ_ARN = Parameter(DLQ_ARN_T, group_label=SQS_SETTINGS, Type="String")

SQS_KMS_KEY_T = "QueueKmsKey"
SQS_KMS_KEY = Parameter(SQS_KMS_KEY_T, group_label=SQS_SETTINGS, Type="String")
