#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Handle association of WebACL to ALB
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.wafv2_webacl.wafv2_webacl_stack import WebACL

from troposphere import GetAtt, Ref
from troposphere.wafv2 import WebACLAssociation

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
)
from ecs_composex.wafv2_webacl.wafv2_webacl_params import WEB_ACL_ARN


def handle_elbv2(
    webacl: WebACL,
    webacl_stack: ComposeXStack,
    target_elbv2: Elbv2,
    elbv2_stack: ComposeXStack,
    settings=None,
    root_stack: ComposeXStack = None,
) -> None:
    """Handles creating an association between ALB & WAFV2 WebACL"""

    if target_elbv2.cfn_resource.Type != "application":
        LOG.warning(
            "%s.%s - Cannot associate LoadBalancer %s - WebACLs only apply to ALB",
            webacl.module.res_key,
            webacl.name,
            target_elbv2.name,
        )
        return
    webacl.init_stack(root_stack, settings)
    if not target_elbv2.attributes_outputs:
        target_elbv2.init_outputs()
        target_elbv2.generate_outputs()
        add_outputs(elbv2_stack.stack_template, target_elbv2.outputs)
    lb_id = target_elbv2.attributes_outputs[target_elbv2.ref_parameter]
    add_parameters(webacl_stack.stack_template, [lb_id["ImportParameter"]])
    webacl_stack.Parameters.update(
        {lb_id["ImportParameter"].title: lb_id["ImportValue"]}
    )
    webacl_arn_id = webacl.attributes_outputs[WEB_ACL_ARN]
    association = add_resource(
        webacl_stack.stack_template,
        WebACLAssociation(
            f"{target_elbv2.logical_name}{webacl.logical_name}Association",
            ResourceArn=Ref(lb_id["ImportParameter"]),
            WebACLArn=GetAtt(webacl.cfn_resource, WEB_ACL_ARN.return_value)
            if webacl.cfn_resource
            else webacl_arn_id["ImportValue"],
        ),
    )
    print(association)
