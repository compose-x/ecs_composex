#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.compose.x_resources import Parameter

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

LABEL = "CodeGuru Profiler"

PROFILER_NAME = Parameter("ProfileName", group_label=LABEL, Type="String")
PROFILER_ARN = Parameter(
    "ProfileArn", group_label=LABEL, return_value="Arn", Type="String"
)
