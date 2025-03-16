#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService

from troposphere.elasticloadbalancingv2 import TargetGroup

from .targets_common import generate_tg_outputs, set_new_tg_output, set_tg_outputs


class ComposeTargetGroup(TargetGroup):
    """
    Class to manage Target Groups
    """

    def __init__(
        self,
        title: str,
        elbv2: Elbv2,
        family: ComposeFamily,
        service: ComposeService,
        stack: ComposeXStack,
        port: int,
        **kwargs,
    ):
        self.family: ComposeFamily = family
        self.service: ComposeService = service
        self.stack: ComposeXStack = stack
        self.port: int = port
        self.outputs = []
        self.elbv2: Elbv2 = elbv2
        self.output_properties = {}
        self.attributes_outputs = {}
        super().__init__(title, **kwargs)

    def init_outputs(self):
        set_tg_outputs(self)

    def generate_outputs(self):
        generate_tg_outputs(self)

    def set_new_resource_outputs(self, output_definition):
        return set_new_tg_output(output_definition)
