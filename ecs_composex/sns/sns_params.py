#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@compose-x.io>
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
from ecs_composex.ecs_composex import X_KEY
from ecs_composex.common.cfn_params import Parameter


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
