#  -*- coding: utf-8 -*-
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
from ecs_composex.ecs_composex import X_KEY
from troposphere import Parameter

TABLE_NAME_T = "DynamoDbTableName"
TABLE_NAME = Parameter(TABLE_NAME_T, Type="String", AllowedPattern=r"[a-zA-Z0-9_.-]+")

TABLE_ARN_T = "DynamoDbTableArn"
TABLE_ARN = Parameter(TABLE_ARN_T, Type="String")

RES_KEY = f"{X_KEY}{path.basename(path.dirname(path.abspath(__file__)))}"
TABLE_SSM_PREFIX = f"/{RES_KEY}/"
