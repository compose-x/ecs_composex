# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module for x-route53
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.route53.route53_helpers import resolve_lookup
from ecs_composex.route53.route53_zone import HostedZone


class XStack(ComposeXStack):
    """
    Root stack for x-route53 hosted zones

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    def __init__(
        self, name: str, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        """
        :param str name:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        self.x_to_x_mappings = []
        self.x_resource_class = HostedZone
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)
        if module.new_resources:
            self.is_void = False
        else:
            self.is_void = True
        stack_template = build_template(module.res_key)
        super().__init__(module.mapping_key, stack_template, **kwargs)
        for resource in module.resources_list:
            resource.stack = self
