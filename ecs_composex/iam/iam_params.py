#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

import re
from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

ROLE_ID_RE = re.compile(r"^[A-Z0-9]+$")

POLICY_RE = re.compile(
    r"((^([a-zA-Z0-9-_./]+)$)|(^(arn:aws:iam::(aws|\d{12}):policy/)[a-zA-Z0-9-_./]+$))"
)


IAM_ROLE_T = "IamRoleName"
IAM_ROLE = Parameter(IAM_ROLE_T, return_value=None, Type="String")

IAM_ROLE_ARN_T = "IamRoleArn"
IAM_ROLE_ARN = Parameter(IAM_ROLE_ARN_T, return_value="Arn", Type="String")

IAM_ROLE_ID_T = "IamRoleId"
IAM_ROLE_ID = Parameter(
    IAM_ROLE_ID_T,
    return_value="RoleId",
    Type="String",
    AllowedPattern=ROLE_ID_RE.pattern,
)
