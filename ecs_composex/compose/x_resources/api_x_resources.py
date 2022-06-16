#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule, ModManager
    from ecs_composex.common.stacks import ComposeXStack


from ecs_composex.common.logging import LOG
from ecs_composex.compose.x_resources.services_resources import ServicesXResource
from ecs_composex.resource_settings import handle_resource_to_services


class ApiXResource(ServicesXResource):
    """
    Class for Resources that only require API / IAM access to be defined
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.predefined_resource_service_scaling_function = None

    def to_ecs(
        self,
        settings: ComposeXSettings,
        modules: ModManager,
        root_stack: ComposeXStack = None,
        targets_overrides: list = None,
    ) -> None:
        """
        Maps API only based resource to ECS Services
        """
        LOG.info(f"{self.module.res_key}.{self.name} - Linking to services")
        handle_resource_to_services(
            settings,
            self,
            arn_parameter=self.arn_parameter,
            nested=False,
            targets_overrides=targets_overrides,
        )
        if self.predefined_resource_service_scaling_function:
            self.predefined_resource_service_scaling_function(self, settings)
