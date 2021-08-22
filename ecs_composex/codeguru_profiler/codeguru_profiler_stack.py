﻿#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage top level AWS CodeGuru profiles
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub
from troposphere.codeguruprofiler import ProfilingGroup

from ecs_composex.codeguru_profiler.codeguru_profiler_ecs import (
    define_lookup_profile_mappings,
)
from ecs_composex.codeguru_profiler.codeguru_profiler_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    PROFILER_ARN,
    PROFILER_NAME,
    RES_KEY,
)
from ecs_composex.codeguru_profiler.codeguru_profiler_perms import ACCESS_TYPES
from ecs_composex.common import build_template
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resources_import import import_record_properties


def create_root_template(new_resources):
    """
    Function to create the root stack template for profiles
    :param new_resources:
    :return:
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
        root_tpl.add_resource(res.cfn_resource)
    return root_tpl


class CodeProfiler(XResource):
    """
    Class to manage AWS Code Guru profiles
    """

    policies_scaffolds = ACCESS_TYPES

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
        for count, env_name in enumerate(self.env_names):
            if env_name == self.name.replace("-", "_"):
                self.env_names.pop(count)
                break
        self.env_names.append("AWS_CODEGURU_PROFILER_GROUP_NAME")
        self.init_env_names(add_self_default=False)

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
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = create_root_template(new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            define_lookup_profile_mappings(
                settings.mappings[RES_KEY], lookup_resources, settings
            )
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
