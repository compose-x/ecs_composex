#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

import re
from os import path

from ecs_composex.common.compose_resources import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = re.sub(r"[^a-zA-Z0-9]", "", MOD_KEY)

USERPOOL_ID = Parameter("UserPoolId", Type="String")
USERPOOL_ARN = Parameter("UserPoolArn", return_value="Arn", Type="String")
USERPOOL_PROVIDER_NAME = Parameter(
    "UserPoolProviderName", return_value="ProviderName", Type="String"
)
USERPOOL_PROVIDER_URL = Parameter(
    "UserPoolProviderUrl", return_value="ProviderURL", Type="String"
)
USERPOOL_DOMAIN = Parameter("UserPoolDomain", Type="String")
