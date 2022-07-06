#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage top level AWS CodeGuru profiles
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub, Template
from troposphere.codeguruprofiler import ProfilingGroup

from ecs_composex.codeguru_profiler.codeguru_profiler_aws import lookup_profile_config
from ecs_composex.codeguru_profiler.codeguru_profiler_params import (
    PROFILER_ARN,
    PROFILER_NAME,
)
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_resource,
    build_template,
)
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.resources_import import import_record_properties


def create_root_template(new_resources: list, module_res_key: str) -> Template:
    """
    Function to create the root stack template for profiles

    :param list[CodeProfiler] new_resources:
    :param str module_res_key:
    :return: The template wit the profiles
    :rtype: troposphere.Template
    """
    root_tpl = build_template(f"Root stack to manage {module_res_key}")
    for res in new_resources:
        try:
            props = import_record_properties(
                res.properties, ProfilingGroup, ignore_missing_required=False
            )
            if res.parameters and keyisset("AppendStackId", res.parameters):
                props["ProfilingGroupName"] = Sub(
                    f"{res.properties['ProfilingGroupName']}-${{StackId}}",
                    StackId=STACK_ID_SHORT,
                )
        except KeyError:
            props = import_record_properties(
                res.properties, ProfilingGroup, ignore_missing_required=True
            )
            props["ProfilingGroupName"] = Sub(
                f"{res.logical_name}-${{StackId}}", StackId=STACK_ID_SHORT
            )
        res.cfn_resource = ProfilingGroup(res.logical_name, **props)
        res.init_outputs()
        res.generate_outputs()
        add_outputs(root_tpl, res.outputs)
        add_resource(root_tpl, res.cfn_resource)
    return root_tpl


class CodeProfiler(ApiXResource):
    """
    Class to manage AWS Code Guru profiles
    """

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        super().__init__(name, definition, module, settings)
        self.arn_parameter = PROFILER_ARN
        self.ref_parameter = PROFILER_NAME

    def init_outputs(self):
        self.output_properties = {
            PROFILER_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            PROFILER_ARN: (
                f"{self.logical_name}{PROFILER_ARN.title}",
                self.cfn_resource,
                GetAtt,
                PROFILER_ARN.return_value,
            ),
        }


def define_lookup_profile_mappings(
    mappings: dict, resources: list[CodeProfiler], settings: ComposeXSettings
):
    """
    Function to update the mappings of CodeGuru profile identified via Lookup
    :param dict mappings:
    :param list resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for res in resources:
        mapping = lookup_profile_config(res.lookup, settings.session)
        if mapping:
            res.mappings = mapping
            res.mappings.update({res.logical_name: mapping[PROFILER_NAME.title]})
            mappings.update({res.logical_name: mapping})


class XStack(ComposeXStack):
    """
    Method to manage the elastic cache resources and root stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        """
        Init method

        :param str title:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param kwargs:
        """

        if module.lookup_resources:
            if not keyisset(module.mapping_key, settings.mappings):
                settings.mappings[module.mapping_key] = {}
            define_lookup_profile_mappings(
                settings.mappings[module.mapping_key], module.lookup_resources, settings
            )

        if module.new_resources:
            stack_template = create_root_template(module.new_resources, module.res_key)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True

        for resource in module.resources_list:
            resource.stack = self
