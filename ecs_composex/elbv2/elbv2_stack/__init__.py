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

from compose_x_common.aws.elasticloadbalancing import LB_V2_LB_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import Ref
from troposphere.elasticloadbalancingv2 import LoadBalancer as CfnLoadBalancer

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import add_update_mapping, build_template
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
        stack_template = init_elbv2_template()
        lb_input = {
            VPC_ID.title: Ref(VPC_ID),
            APP_SUBNETS.title: Ref(APP_SUBNETS),
            PUBLIC_SUBNETS.title: Ref(PUBLIC_SUBNETS),
        }
        if module.new_resources:
            for resource in module.new_resources:
                resource.set_lb_definition()
                resource.sort_alb_ingress(settings, stack_template)

        self.is_void = False
        super().__init__(title, stack_template, stack_parameters=lb_input, **kwargs)
        for resource in module.resources_list:
            resource.stack = self

        if not hasattr(self, "DeletionPolicy"):
            setattr(self, "DeletionPolicy", module.module_deletion_policy)

        if module.lookup_resources and not module.mapping_key in settings.mappings:
            settings.mappings[module.mapping_key] = {}

        for resource in module.lookup_resources:
            resource.lookup_resource(
                LB_V2_LB_ARN_RE,
                None,
                cfn_resource_type=CfnLoadBalancer.resource_type,
                tagging_api_id="elasticloadbalancing:loadbalancer",
                subattribute_key="loadbalancer",
                use_arn_for_id=True,
            )
            if keyisset("Listeners", resource.lookup):
                resource.find_lookup_listeners()

            resource.generate_cfn_mappings_from_lookup_properties()
            resource.generate_outputs()
            settings.mappings[module.mapping_key].update(
                {resource.logical_name: resource.mappings}
            )
            resource.sort_alb_ingress(settings, stack_template)
