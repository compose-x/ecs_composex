#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from os import path
from troposphere import Parameter

RES_KEY = f"x-{path.basename(path.dirname(path.abspath(__file__)))}"

KMS_KEY_ARN_RE = re.compile(
    r"(?:^arn:aws(?:-[a-z]+)?:kms:[\S]+:[0-9]+:)((key/)([\S]+))$"
)
KMS_ALIAS_ARN_RE = re.compile(
    r"(?:^arn:aws(?:-[a-z]+)?:kms:[\S]+:[0-9]+:)((alias/)([\S]+))$"
)

KMS_KEY_ARN_T = "Arn"
KMS_KEY_ID_T = "KeyId"
KMS_KEY_ALIAS_NAME_T = "KmsKeyAliasName"
KMS_KEY_ALIAS_ARN_T = "KmsKeyAliasName"

KMS_KEY_ARN = Parameter(KMS_KEY_ARN_T, Type="String")
KMS_KEY_ID = Parameter(KMS_KEY_ID_T, Type="String")
KMS_KEY_ALIAS_NAME = Parameter(KMS_KEY_ALIAS_NAME_T, Type="String")
KMS_KEY_ALIAS_ARN = Parameter(KMS_KEY_ALIAS_ARN_T, Type="String")
