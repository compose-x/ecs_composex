#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .cloudmap_stack import PrivateNamespace, XStack

COMPOSE_X_MODULES: dict = {
    "x-cloudmap": {
        "Module": XResourceModule(
            "x-cloudmap",
            XStack,
            Path(path.abspath(path.dirname(__file__))),
            PrivateNamespace,
        ),
    },
}
