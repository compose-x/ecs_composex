#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re
from os import path

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
SSM_PREFIX = f"/{RES_KEY}/"

TOPIC_ARN_RE = re.compile(r"(^arn:aws(?:-[a-z]+)?:sns:[\S]+:[0-9]+:[\S]+)$")

TOPIC_ARN_T = "TopicArn"
TOPIC_NAME_T = "TopicName"
TOPIC_KMS_KEY_T = "TopicKmsKey"

TOPIC_ARN = Parameter(TOPIC_ARN_T, Type="String")
TOPIC_NAME = Parameter(TOPIC_NAME_T, return_value="TopicName", Type="String")
TOPIC_KMS_KEY = Parameter(TOPIC_KMS_KEY_T, Type="String")
