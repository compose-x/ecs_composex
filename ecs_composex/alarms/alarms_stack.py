# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module to create x-alarms defined at the top level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ecs_composex.alarms.alarms_helpers import create_alarms

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

import warnings

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref
from troposphere.cloudwatch import CompositeAlarm

from ecs_composex.alarms.alarms_elbv2 import (
    handle_elbv2_dimension_mapping,
    handle_elbv2_target_group_dimensions,
)
from ecs_composex.alarms.alarms_params import ALARM_ARN, ALARM_NAME
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.compose.x_resources.services_resources import ServicesXResource


class Alarm(ServicesXResource):
    """
    Class to represent CW Alarms
    """

    topics_key = "Topics"

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        self.topics = []
        self.is_composite = False
        self.in_composite = False
        super().__init__(name, definition, module, settings)
        self.topics = (
            definition[self.topics_key]
            if keyisset(self.topics_key, self.definition)
            else []
        )

    def init_outputs(self):
        self.output_properties = {
            ALARM_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            ALARM_ARN: (
                f"{self.logical_name}{ALARM_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                ALARM_ARN.return_value,
            ),
        }

    def handle_dimensions(self, settings: ComposeXSettings) -> None:
        """
        Handles the dimensions settings and tries to resolve

        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        if not hasattr(self.cfn_resource, "Dimensions"):
            LOG.debug(f"{self.module.res_key}.{self.name} - No Dimensions defined")
            return
        dimensions = getattr(self.cfn_resource, "Dimensions")
        namespace = self.cfn_resource.Namespace
        if namespace == "AWS/ApplicationELB" or namespace == "AWS/NetworkELB":
            for dimension in dimensions:
                if dimension.Name == "LoadBalancer" and dimension.Value.startswith(
                    r"x-elbv2::"
                ):
                    handle_elbv2_dimension_mapping(
                        self.stack, dimension, self, settings
                    )
                elif dimension.Name == "TargetGroup" and dimension.Value.startswith(
                    r"x-elbv2::"
                ):
                    handle_elbv2_target_group_dimensions(
                        self.stack, dimension, self, settings
                    )

    def handle_x_dependencies(
        self, settings: ComposeXSettings, root_stack: ComposeXStack = None
    ) -> None:
        """
        Function to cross reference alarm settings with other resources

        :param ecs_composex.common.stacks.ComposeXStacks root_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """

        if (
            isinstance(self, Alarm)
            and isinstance(self.cfn_resource, CompositeAlarm)
            or not self.cfn_resource
        ):
            return
        self.handle_dimensions(settings)


class XStack(ComposeXStack):
    """
    Class to represent the root stack for alarms
    """

    def __init__(
        self, name, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.new_resources:
            template = build_template("Root stack for Alarms created via Compose-X")
            super().__init__(name, stack_template=template, **kwargs)
            create_alarms(template, module.new_resources)
        else:
            self.is_void = True
        if module.lookup_resources:
            warnings.warn(
                f"{module.res_key} - Lookup and Use are not supported. "
                "You can only create new resources"
            )
        for resource in module.resources_list:
            resource.stack = self
