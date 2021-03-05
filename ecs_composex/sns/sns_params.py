# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from os import path
from ecs_composex.ecs_composex import X_KEY
from ecs_composex.common.cfn_params import Parameter


MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
SSM_PREFIX = f"/{RES_KEY}/"

TOPIC_ARN_T = "TopicArn"
TOPIC_NAME_T = "TopicName"
TOPIC_KMS_KEY_T = "TopicKmsKey"

TOPIC_ARN = Parameter(TOPIC_ARN_T, Type="String")
TOPIC_NAME = Parameter(TOPIC_NAME_T, return_value="TopicName", Type="String")
TOPIC_KMS_KEY = Parameter(TOPIC_KMS_KEY_T, Type="String")
