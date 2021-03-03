# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@compose-x.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" Parameters for SQS"""

from os import path
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
SQS_SSM_PREFIX = f"/{RES_KEY}/"

SQS_URL_T = "Url"
SQS_URL = Parameter(SQS_URL_T, Type="String")

SQS_ARN_T = "Arn"
SQS_ARN = Parameter(SQS_ARN_T, return_value="Arn", Type="String")

SQS_NAME_T = "QueueName"
SQS_NAME = Parameter(SQS_NAME_T, return_value="QueueName", Type="String")

DLQ_NAME_T = "DeadLetterQueueName"
DLQ_NAME = Parameter(DLQ_NAME_T, Type="String")

DLQ_ARN_T = "DeadLetterQueueArn"
DLQ_ARN = Parameter(DLQ_ARN_T, Type="String")

SQS_KMS_KEY_T = "QueueKmsKey"
SQS_KMS_KEY = Parameter(SQS_KMS_KEY_T, Type="String")
