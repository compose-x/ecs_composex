# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import GetAtt, Ref

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.sns.sns_helpers import create_sns_mappings
from ecs_composex.sns.sns_params import TOPIC_ARN, TOPIC_NAME
from ecs_composex.sns.sns_templates import generate_sns_templates


class Topic(ApiXResource):
    """
    Class for SNS Topics
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.arn_parameter = TOPIC_ARN
        self.ref_parameter = TOPIC_ARN
        self.support_defaults = True

    def init_outputs(self):
        self.output_properties = {
            TOPIC_ARN: (self.logical_name, self.cfn_resource, Ref, None),
            TOPIC_NAME: (
                f"{self.logical_name}{TOPIC_NAME.title}",
                self.cfn_resource,
                GetAtt,
                TOPIC_NAME.return_value,
            ),
        }


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            create_sns_mappings(module.lookup_resources, settings, module)

        if not module.new_resources:
            self.is_void = True
        else:
            template = build_template(
                f"{module.res_key} - Compose-X Generated template"
            )
            generate_sns_templates(settings, module.new_resources, self, template)
            super().__init__(module.mapping_key, stack_template=template, **kwargs)
        for resource in module.resources_list:
            resource.stack = self
