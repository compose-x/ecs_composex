#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from os import path

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"x-{MOD_KEY}"

SSM_PARAM_NAME_T = "ParameterName"
SSM_PARAM_NAME = Parameter(SSM_PARAM_NAME_T, Type="String")

SSM_PARAM_TYPE_T = "ParameterType"
SSM_PARAM_TYPE = Parameter(
    SSM_PARAM_TYPE_T,
    return_value="Type",
    Type="String",
    AllowedValues=["String", "StringList", "SecureString"],
)
