#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.common.settings import ComposeXSettings

from ecs_composex.compose.x_resources import XResource


class AwsEnvironmentResource(XResource):
    """
    Class for AWS Resources that are used by other AWS Resources. The services do not use these resources directly

    :ivar bool lookup_only: Whether the XResource should only be looked up.
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        self.lookup_only = False
        super().__init__(name, definition, module, settings)
        self.requires_vpc = False
        self.arn_parameter = None
