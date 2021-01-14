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

"""
Module for Secrets parameters
"""

from troposphere import Parameter

RES_KEY = "secrets"
XRES_KEY = "x-secrets"

PASSWORD_LENGTH_T = "PasswordLength"
PASSWORD_LENGTH = Parameter(
    PASSWORD_LENGTH_T, Type="Number", MinValue=8, MaxValue=32, Default=16
)

USERNAME_T = "Username"
USERNAME = Parameter(
    USERNAME_T, Type="String", MinLength=3, MaxLength=16, Default="dbadmin"
)
