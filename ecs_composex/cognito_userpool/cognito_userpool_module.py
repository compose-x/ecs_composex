#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .cognito_userpool_stack import UserPool, XStack

COMPOSE_X_MODULES: dict = {
    "x-cognito_userpool": {
        "Module": XResourceModule(
            "x-cognito_userpool",
            XStack,
            Path(path.abspath(path.dirname(__file__))),
            UserPool,
        ),
    },
}
