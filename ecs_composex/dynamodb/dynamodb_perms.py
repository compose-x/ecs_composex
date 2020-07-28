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

"""
Set of functions to generate permissions to access queues
based on pre-defined TABLE policies for consumers
"""

ACCESS_TYPES = {
    "RW": {
        "Action": [
            "dynamodb:BatchGet*",
            "dynamodb:DescribeStream",
            "dynamodb:DescribeTable",
            "dynamodb:Get*",
            "dynamodb:Query",
            "dynamodb:Scan",
            "dynamodb:BatchWrite*",
            "dynamodb:DeleteItem",
            "dynamodb:UpdateItem",
            "dynamodb:PutItem",
        ],
        "Effect": "Allow",
    },
    "RO": {
        "Action": ["dynamodb:DescribeTable", "dynamodb:Query", "dynamodb:Scan"],
        "Effect": "Allow",
    },
    "PowerUser": {
        "NotAction": [
            "dynamodb:CreateTable",
            "dynamodb:DeleteTable",
            "dynamodb:DeleteBackup",
        ]
    },
}
