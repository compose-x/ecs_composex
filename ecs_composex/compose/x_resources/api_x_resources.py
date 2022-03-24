#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common import LOG
from ecs_composex.compose.x_resources.services_resources import ServicesXResource
from ecs_composex.resource_settings import handle_resource_to_services


class ApiXResource(ServicesXResource):
    """
    Class for Resources that only require API / IAM access to be defined
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.predefined_resource_service_scaling_function = None

    def to_ecs(self, settings, root_stack=None) -> None:
        """
        Maps API only based resource to ECS Services
        """
        LOG.debug(f"{self.module_name}.{self.name} - Linking to services")
        handle_resource_to_services(
            settings,
            self,
            arn_parameter=self.arn_parameter,
            nested=False,
        )
        if self.predefined_resource_service_scaling_function:
            self.predefined_resource_service_scaling_function(self, settings)
