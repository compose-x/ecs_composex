#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Manages to add the SSM Parameter for FireLens configuration
"""

from __future__ import annotations

from json import dumps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings

from ecs_composex.common.troposphere_tools import add_outputs, add_resource
from ecs_composex.ssm_parameter.ssm_parameter_helpers import render_new_parameters
from ecs_composex.ssm_parameter.ssm_parameter_stack import SsmParameter


def add_managed_ssm_parameter(
    family: ComposeFamily, settings: ComposeXSettings, content: dict
) -> SsmParameter:
    """
    Handles x-logging.FireLens.Advanced.Rendered

    :param family:
    :param settings:
    :param content:
    """

    ssm_parameter_title = f"{family.logical_name}FireLensConfigurationSsm"
    ssm_parameter_definition = {
        "Properties": {
            "DataType": "text",
            "Type": "String",
            "Value": dumps(content),
        },
        "MacroParameters": {"EncodeToBase64": True},
        "Services": {family.name: {"Access": "RO"}},
    }

    if "x-ssm_parameter" not in settings.mod_manager.modules:
        x_ssm_content: dict = {ssm_parameter_title: ssm_parameter_definition}
        ssm_module = settings.mod_manager.load_module(
            "x-ssm_parameter", res_def=x_ssm_content
        )
        settings.compose_content[ssm_module.res_key] = ssm_module.definition
        ssm_module.set_resources(settings)
    else:
        ssm_module = settings.mod_manager.modules["x-ssm_parameter"]
        settings.compose_content[ssm_module.res_key].update(
            {ssm_parameter_title: ssm_parameter_definition}
        )
    if not ssm_module:
        raise LookupError("Failed to import x-ssm_parameter module!")

    if ssm_module.mapping_key not in settings.stacks:
        ssm_stack = ssm_module.stack_class(ssm_module.mod_key, settings, ssm_module)
        settings.stacks[ssm_module.mapping_key] = ssm_stack
        add_resource(settings.root_stack.stack_template, ssm_stack)
        ssm_parameter = settings.find_resource(
            f"x-ssm_parameter::{ssm_parameter_title}"
        )
    else:
        ssm_stack = settings.stacks[ssm_module.mapping_key]
        ssm_parameter = SsmParameter(
            ssm_parameter_title, ssm_parameter_definition, ssm_module, settings
        )
        render_new_parameters([ssm_parameter], ssm_stack)
        ssm_parameter.stack = ssm_stack
        ssm_parameter.init_outputs()
        ssm_parameter.generate_outputs()
        add_resource(ssm_parameter.stack.stack_template, ssm_parameter.cfn_resource)
        add_outputs(ssm_parameter.stack.stack_template, ssm_parameter.outputs)
        ssm_parameter.to_ecs(settings, settings.mod_manager)
        settings.compose_content[ssm_module.res_key][ssm_parameter.name] = ssm_parameter
        ssm_module.resources[ssm_parameter_title] = ssm_parameter

    return ssm_parameter
