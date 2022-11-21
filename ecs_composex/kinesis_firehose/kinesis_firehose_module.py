#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path
from pathlib import Path

from ecs_composex.mods_manager import XResourceModule

from .kinesis_firehose_stack import DeliveryStream, XStack

COMPOSE_X_MODULES: dict = {
    "x-kinesis_firehose": {
        "Module": XResourceModule(
            "x-kinesis_firehose",
            XStack,
            Path(path.abspath(path.dirname(__file__))),
            DeliveryStream,
        ),
    },
}
