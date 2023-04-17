#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule
from ecs_composex.wafv2_webacl.wafv2_webacl_stack import WebACL, XStack

COMPOSE_X_MODULES: dict = {
    "x-wafv2_webacl": {
        "Module": XResourceModule(
            "x-wafv2_webacl",
            XStack,
            Path(path.abspath(path.dirname(__file__))),
            WebACL,
        ),
    },
}
