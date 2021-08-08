#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage top level AWS CodeGuru profiles
"""

from troposphere import GetAtt, Ref

from ecs_composex.codeguru_profiler.codeguru_profiler_perms import ACCESS_TYPES
from ecs_composex.cognito_userpool.cognito_aws import lookup_userpool_config
from ecs_composex.cognito_userpool.cognito_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    USERPOOL_ARN,
    USERPOOL_ID,
)
from ecs_composex.common import build_template
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack


def create_root_template(new_resources):
    """
    Function to create the root stack template for profiles
    :param new_resources:
    :return:
    """
    root_tpl = build_template(f"Root stack to manage {MOD_KEY}")
    return root_tpl


class UserPool(XResource):
    """
    Class to manage AWS Code Guru profiles
    """

    policies_scaffolds = ACCESS_TYPES

    def init_outputs(self):
        self.output_properties = {
            USERPOOL_ID: (self.logical_name, self.cfn_resource, Ref, None),
            USERPOOL_ARN: (
                f"{self.logical_name}{USERPOOL_ARN.title}",
                self.cfn_resource,
                GetAtt,
                USERPOOL_ARN.return_value,
            ),
        }


class XStack(ComposeXStack):
    """
    Method to manage the elastic cache resources and root stack
    """

    def __init__(self, title, settings, **kwargs):
        """
        :param title:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param kwargs:
        """
        set_resources(settings, UserPool, RES_KEY, MOD_KEY)
        new_resources = [
            res
            for res in settings.compose_content[RES_KEY].values()
            if not res.lookup and not res.use
        ]
        if new_resources:
            stack_template = create_root_template(new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
        lookup_resources = [
            res
            for res in settings.compose_content[RES_KEY].values()
            if res.lookup and not res.use and not res.properties
        ]
        for res in lookup_resources:
            self.mappings[res.logical_name] = lookup_userpool_config(
                res.lookup, settings.session
            )
        settings.mappings[MAPPINGS_KEY] = self.mappings
