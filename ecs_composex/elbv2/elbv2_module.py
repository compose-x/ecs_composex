#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .elbv2_stack import Elbv2, XStack

COMPOSE_X_MODULES: dict = {
    "x-elbv2": {
        "Module": XResourceModule(
            "x-elbv2", XStack, Path(path.abspath(path.dirname(__file__))), Elbv2
        ),
    },
}
