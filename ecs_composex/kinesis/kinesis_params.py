﻿#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from os import path
from troposphere import Parameter
from ecs_composex.ecs_composex import X_KEY


RES_KEY = f"{X_KEY}{path.basename(path.dirname(path.abspath(__file__)))}"

STREAM_ID_T = "StreamId"
STREAM_ARN_T = "Arn"
STREAM_KMS_KEY_ID_T = "KmsKeyId"

STREAM_ID = Parameter(STREAM_ID_T, Type="String")
STREAM_ARN = Parameter(STREAM_ARN_T, Type="String")
STREAM_KMS_KEY_ID = Parameter(STREAM_KMS_KEY_ID_T, Type="String")
