#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .opensearch_stack import OpenSearchDomain, XStack

COMPOSE_X_MODULES: dict = {
    "x-opensearch'": {
        "Module": XResourceModule(
            "x-opensearch",
            XStack,
            Path(path.abspath(path.dirname(__file__))),
            OpenSearchDomain,
        ),
    },
}
