#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ecs.ecs_family import ComposeFamily

from troposphere import Ref

from ecs_composex.common.troposphere_tools import add_outputs, add_parameters
from ecs_composex.elbv2.elbv2_params import LB_SG_ID


def handle_sg_lb_ingress_to_service(
    resource, family: ComposeFamily, resources_stack: ComposeXStack
) -> None:
    """
    Function to add ingress from the LB to Target if using ALB
    """
    if resource.is_nlb():
        return
    if resource.cfn_resource and not resource.attributes_outputs:
        resource.init_outputs()
        resource.generate_outputs()
    lb_sg_param = resource.attributes_outputs[LB_SG_ID]["ImportParameter"]
    add_parameters(family.template, [lb_sg_param])
    family.service_networking.add_lb_ingress(
        lb_name=resource.logical_name, lb_sg_ref=Ref(lb_sg_param)
    )
    family.stack.Parameters.update(
        {lb_sg_param.title: resource.attributes_outputs[LB_SG_ID]["ImportValue"]}
    )
    if resources_stack.title not in family.stack.DependsOn:
        family.stack.DependsOn.append(resources_stack.title)


def setup_template(load_balancer: Elbv2, res_root_stack: ComposeXStack) -> Template:
    """
    Sets up the CloudFormation template for a load balancer by configuring listeners and outputs.

    Args:
        load_balancer (Elbv2): The load balancer resource to configure
        res_root_stack (ComposeXStack): The root stack containing the template

    Returns:
        Template: The configured CloudFormation template with listeners and outputs added

    """
    template: Template = res_root_stack.stack_template
    load_balancer.set_listeners(template)
    load_balancer.associate_to_template(template)
    add_outputs(template, load_balancer.outputs)
    return template
