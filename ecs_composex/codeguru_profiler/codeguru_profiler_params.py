#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common.compose_resources import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"

PROFILER_NAME = Parameter("ProfileName", Type="String")
PROFILER_ARN = Parameter("ProfileArn", return_value="Arn", Type="String")
