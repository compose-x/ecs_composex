#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re
from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

KMS_KEY_ARN_RE = re.compile(
    r"(?:^arn:aws(?:-[a-z]+)?:kms:[\S]+:[0-9]+:)((key/)([\S]+))$"
)
KMS_ALIAS_ARN_RE = re.compile(
    r"(?:^arn:aws(?:-[a-z]+)?:kms:[\S]+:[0-9]+:)((alias/)([\S]+))$"
)

KMS_KEY_ARN_T = "KmsKeyArn"
KMS_KEY_ID_T = "KmsKeyId"
KMS_KEY_ALIAS_NAME_T = "KmsKeyAliasName"
KMS_KEY_ALIAS_ARN_T = "KmsKeyAliasArn"

KMS_KEY_ID = Parameter(KMS_KEY_ID_T, Type="String")
KMS_KEY_ARN = Parameter(KMS_KEY_ARN_T, return_value="Arn", Type="String")
KMS_KEY_ALIAS_NAME = Parameter(KMS_KEY_ALIAS_NAME_T, Type="String")
