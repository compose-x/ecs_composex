#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage top level AWS CodeGuru profiles
"""
import warnings

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub, Template
from troposphere.codeguruprofiler import ProfilingGroup

from ecs_composex.codeguru_profiler.codeguru_profiler_aws import lookup_profile_config
from ecs_composex.codeguru_profiler.codeguru_profiler_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    PROFILER_ARN,
    PROFILER_NAME,
    RES_KEY,
)
from ecs_composex.common import add_outputs, build_template
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.resources_import import import_record_properties


def create_root_template(new_resources: list) -> Template:
    """
    Function to create the root stack template for profiles

    :param list[CodeProfiler] new_resources:
    :return: The template wit the profiles
    :rtype: troposphere.Template
    """
    root_tpl = build_template(f"Root stack to manage {MOD_KEY}")
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
        root_tpl.add_resource(res.cfn_resource)
    return root_tpl


class CodeProfiler(ApiXResource):
    """
    Class to manage AWS Code Guru profiles
    """

    policies_scaffolds = get_access_types(MOD_KEY)

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
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


def define_lookup_profile_mappings(mappings, resources, settings):
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

    def __init__(self, title, settings, **kwargs):
        """
        Init method

        :param str title:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param kwargs:
        """
        set_resources(settings, CodeProfiler, RES_KEY, MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if use_resources:
            warnings.warn(f"{RES_KEY} does not yet support Use.")
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        if lookup_resources:
            if not keyisset(MAPPINGS_KEY, settings.mappings):
                settings.mappings[MAPPINGS_KEY] = {}
            define_lookup_profile_mappings(
                settings.mappings[MAPPINGS_KEY], lookup_resources, settings
            )
        new_resources = set_new_resources(x_resources, RES_KEY, False)

        if new_resources:
            stack_template = create_root_template(new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True

        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
