#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for Secrets parameters
"""

from ecs_composex.common.cfn_params import Parameter

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
