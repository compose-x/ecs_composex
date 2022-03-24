#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.compose.x_resources import XResource


class AwsEnvironmentResource(XResource):
    """
    Class for AWS Resources that are used by other AWS Resources. The services do not use these resources directly

    :ivar bool lookup_only: Whether the XResource should only be looked up.
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        self.lookup_only = False
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.requires_vpc = False
        self.arn_parameter = None
