# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for the XStack SSM
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.aws.ssm_parameter import SSM_PARAMETER_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, Ref, Sub
from troposphere.ssm import Parameter as CfnSsmParameter

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.ssm_parameter.ssm_parameter_helpers import (
    get_parameter_config,
    render_new_parameters,
)
from ecs_composex.ssm_parameter.ssm_parameter_params import (
    SSM_PARAM_ARN,
    SSM_PARAM_NAME,
)


class SsmParameter(ApiXResource):
    """
    Class to represent a SSM Parameter
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.ref_parameter = SSM_PARAM_NAME
        self.arn_parameter = SSM_PARAM_ARN

    def init_outputs(self):
        spacer = ""
        if (
            self.properties
            and keyisset("Name", self.properties)
            and not self.properties["Name"].startswith(r"/")
        ) or not keyisset("Name", self.properties):
            spacer = "/"
        self.output_properties = {
            SSM_PARAM_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            SSM_PARAM_ARN: (
                f"{self.logical_name}{SSM_PARAM_ARN.title}",
                self.cfn_resource,
                Sub,
                f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:parameter{spacer}"
                f"${{{self.cfn_resource.title}}}",
            ),
        }


def resolve_lookup(lookup_resources, settings, module: XResourceModule):
    """
    Lookup of the AWS resources and setting the mappings for the resource type

    :param list lookup_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            SSM_PARAMETER_ARN_RE,
            get_parameter_config,
            CfnSsmParameter.resource_type,
            "ssm:parameter",
        )
        LOG.info(f"{module.res_key}.{resource.name} - Matched to {resource.arn}")
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):

        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)

        if module.new_resources:
            template = build_template("Parent template for SSM in ECS Compose-X")
            super().__init__(module.mapping_key, stack_template=template, **kwargs)
            render_new_parameters(module.new_resources, self)
        else:
            self.is_void = True
        for resource in module.resources_list:
            resource.stack = self
