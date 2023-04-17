#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.wafv2_webacl.wafv2_webacl_stack import WebACL

from troposphere.validators import wafv2 as wafv2_validators

from ecs_composex.common.troposphere_tools import add_outputs
from ecs_composex.resources_import import import_record_properties
from ecs_composex.wafv2_webacl.validators_wafv2 import validate_statement

delattr(wafv2_validators, "validate_statement")
setattr(wafv2_validators, "validate_statement", validate_statement)


def render_new_web_acls(new_resources: list[WebACL], root_stack: ComposeXStack) -> None:
    """
    Imports properties from Compose definition to create resource
    """
    from troposphere.wafv2 import WebACL as CfnWebACL

    for new_res in new_resources:
        param_props = import_record_properties(
            new_res.properties, CfnWebACL, ignore_missing_required=False
        )
        new_res.cfn_resource = CfnWebACL(new_res.logical_name, **param_props)
        root_stack.stack_template.add_resource(new_res.cfn_resource)
        new_res.init_outputs()
        new_res.generate_outputs()
        add_outputs(root_stack.stack_template, new_res.outputs)
