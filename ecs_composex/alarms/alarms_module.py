#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .alarms_stack import Alarm, XStack

COMPOSE_X_MODULES: dict = {
    "x-alarms": {
        "Module": XResourceModule(
            "x-alarms", XStack, Path(path.abspath(path.dirname(__file__))), Alarm
        ),
    },
}
