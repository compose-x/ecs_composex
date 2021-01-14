#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.


from troposphere import Ref, GetAtt

from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kinesis.kinesis_params import (
    STREAM_ID,
    STREAM_ARN,
    RES_KEY,
    STREAM_KMS_KEY_ID,
)
from ecs_composex.kinesis.kinesis_template import create_streams_template
from ecs_composex.kinesis.kinesis_perms import ACCESS_TYPES


class Stream(XResource):
    """
    Class to represent a Kinesis Stream
    """

    policies_scaffolds = ACCESS_TYPES

    def __init__(self, name, definition, settings):
        super().__init__(name, definition, settings)
        self.arn_attr = STREAM_ARN
        self.main_attr = STREAM_ID
        self.kms_arn_attr = STREAM_KMS_KEY_ID

    def init_outputs(self):
        self.output_properties = {
            STREAM_ARN.title: (
                f"{self.logical_name}{STREAM_ARN.title}",
                self.cfn_resource,
                GetAtt,
                STREAM_ARN.title,
            ),
            STREAM_ID.title: (self.logical_name, self.cfn_resource, Ref, None),
        }


class XStack(ComposeXStack):
    """
    Class to represent
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Stream, RES_KEY)
        new_resources = [
            settings.compose_content[RES_KEY][stream_name]
            for stream_name in settings.compose_content[RES_KEY]
            if not settings.compose_content[RES_KEY][stream_name].lookup
        ]
        if new_resources:
            stack_template = create_streams_template(new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
