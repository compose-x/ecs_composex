#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref

from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kinesis.kinesis_ecs import create_kinesis_mappings
from ecs_composex.kinesis.kinesis_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    STREAM_ARN,
    STREAM_ID,
)
from ecs_composex.kinesis.kinesis_perms import ACCESS_TYPES
from ecs_composex.kinesis.kinesis_template import create_streams_template


class Stream(XResource):
    """
    Class to represent a Kinesis Stream
    """

    policies_scaffolds = ACCESS_TYPES

    def init_outputs(self):
        self.output_properties = {
            STREAM_ID: (self.logical_name, self.cfn_resource, Ref, None),
            STREAM_ARN: (
                f"{self.logical_name}{STREAM_ARN.title}",
                self.cfn_resource,
                GetAtt,
                STREAM_ARN.return_value,
            ),
        }


class XStack(ComposeXStack):
    """
    Class to represent
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Stream, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = create_streams_template(new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            create_kinesis_mappings(
                settings.mappings[RES_KEY], lookup_resources, settings
            )
        for resource in x_resources:
            resource.stack = self
