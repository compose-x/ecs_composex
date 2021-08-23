#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

STREAM_ID_T = "StreamId"
STREAM_ARN_T = "Arn"
STREAM_KMS_KEY_ID_T = "KmsKeyId"

STREAM_ID = Parameter(STREAM_ID_T, Type="String")
STREAM_ARN = Parameter(STREAM_ARN_T, return_value="Arn", Type="String")
STREAM_KMS_KEY_ID = Parameter(STREAM_KMS_KEY_ID_T, Type="String")
