#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .events_stack import Rule, XStack

COMPOSE_X_MODULES: dict = {
    "x-events": {
        "Module": XResourceModule(
            "x-events", XStack, Path(path.abspath(path.dirname(__file__))), Rule
        ),
    },
}
