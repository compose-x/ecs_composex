#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from troposphere import GetAtt, Ref

from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kinesis.kinesis_params import MOD_KEY, RES_KEY, STREAM_ARN, STREAM_ID
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
        set_resources(settings, Stream, RES_KEY, MOD_KEY)
        new_resources = [
            stream
            for stream in settings.compose_content[RES_KEY].values()
            if not stream.lookup and not stream.use
        ]
        if new_resources:
            stack_template = create_streams_template(new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
