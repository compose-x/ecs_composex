#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .codeguru_profiler_stack import CodeProfiler, XStack

COMPOSE_X_MODULES: dict = {
    "x-codeguru_profiler": {
        "Module": XResourceModule(
            "x-codeguru_profiler",
            XStack,
            Path(path.abspath(path.dirname(__file__))),
            CodeProfiler,
        ),
    },
}
