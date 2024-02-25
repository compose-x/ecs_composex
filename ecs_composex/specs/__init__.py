#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from referencing.jsonschema import EMPTY_REGISTRY as _EMPTY_REGISTRY

from ecs_composex.specs._core import _schemas

REGISTRY = (_schemas() @ _EMPTY_REGISTRY).crawl()
__all__ = ["REGISTRY"]
