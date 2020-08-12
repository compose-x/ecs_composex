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

from os import path
from json import loads


def get_access_types():
    with open(
        f"{path.abspath(path.dirname(__file__))}/kms_perms.json",
        "r",
        encoding="utf-8-sig",
    ) as perms_fd:
        return loads(perms_fd.read())


ACCESS_TYPES = get_access_types()
