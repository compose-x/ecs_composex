# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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
from troposphere import Parameter

SQS_URL_T = "Url"
SQS_URL = Parameter(SQS_URL_T, Type="String")

SQS_ARN_T = "Arn"
SQS_ARN = Parameter(SQS_ARN_T, Type="String")

SQS_NAME_T = "QueueName"
SQS_NAME = Parameter(SQS_NAME_T, Type="String")

DLQ_NAME_T = "DeadLetterQueueName"
DLQ_NAME = Parameter(DLQ_NAME_T, Type="String")

DLQ_ARN_T = "DeadLetterQueueArn"
DLQ_ARN = Parameter(DLQ_ARN_T, Type="String")

RES_KEY = f"x-{path.basename(path.dirname(path.abspath(__file__)))}"
SQS_SSM_PREFIX = f"/{RES_KEY}/"
