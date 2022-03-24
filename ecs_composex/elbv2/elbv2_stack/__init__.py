#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle elbv2.
"""

import warnings

from troposphere import Ref

from ecs_composex.common import build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.elbv2.elbv2_params import MAPPINGS_KEY, MOD_KEY, RES_KEY
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

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Elbv2, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if lookup_resources or use_resources:
            warnings.warn(
                f"{RES_KEY} - Lookup not supported. You can only create new resources."
            )
        if not new_resources:
            self.is_void = True
            return
        stack_template = init_elbv2_template()
        lb_input = {
            VPC_ID.title: Ref(VPC_ID),
            APP_SUBNETS.title: Ref(APP_SUBNETS),
            PUBLIC_SUBNETS.title: Ref(PUBLIC_SUBNETS),
        }
        for resource in new_resources:
            resource.set_lb_definition()
            resource.sort_alb_ingress(settings, stack_template)

        super().__init__(title, stack_template, stack_parameters=lb_input, **kwargs)
        for resource in new_resources:
            resource.stack = self
