# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle elbv2.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

import warnings

from troposphere import Ref

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.elbv2.elbv2_stack.elbv2 import Elbv2
from ecs_composex.vpc.vpc_params import APP_SUBNETS, PUBLIC_SUBNETS, VPC_ID


def init_elbv2_template():
    """
    Function to create a new root ELBv2 stack
    :return:
    """
    lb_params = [VPC_ID, APP_SUBNETS, PUBLIC_SUBNETS]
    template = build_template("elbv2 root template for ComposeX", lb_params)
    return template


class XStack(ComposeXStack):
    """
    Class to handle ELBv2 resources
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            warnings.warn(
                f"{module.res_key} - Lookup not supported. You can only create new resources."
            )
        if not module.new_resources:
            self.is_void = True
            return
        stack_template = init_elbv2_template()
        lb_input = {
            VPC_ID.title: Ref(VPC_ID),
            APP_SUBNETS.title: Ref(APP_SUBNETS),
            PUBLIC_SUBNETS.title: Ref(PUBLIC_SUBNETS),
        }
        for resource in module.new_resources:
            resource.set_lb_definition()
            resource.sort_alb_ingress(settings, stack_template)

        super().__init__(title, stack_template, stack_parameters=lb_input, **kwargs)
        for resource in module.resources_list:
            resource.stack = self
