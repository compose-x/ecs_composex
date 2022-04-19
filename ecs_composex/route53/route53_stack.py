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

from ecs_composex.common import build_template
from ecs_composex.common.stacks import ComposeXStack
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

    stack_title = "Route53 zones and records created from x-route53"

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
        set_resources(settings, HostedZone, module)
        x_resources = settings.compose_content[module.res_key].values()
        lookup_resources = set_lookup_resources(x_resources)
        if lookup_resources:
            resolve_lookup(lookup_resources, settings, module)
        new_resources = set_new_resources(x_resources, False)
        if new_resources:
            stack_template = build_template(self.stack_title)
            super().__init__(module.mapping_key, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in x_resources:
            resource.stack = self
