#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

"""
Module to control S3 stack
"""

from troposphere import Ref, GetAtt
from troposphere.s3 import Bucket as S3Bucket

from ecs_composex.common import LOG, keyisset, build_template, NONALPHANUM
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.s3.s3_params import RES_KEY, S3_BUCKET_NAME, S3_BUCKET_ARN
from ecs_composex.s3.s3_template import generate_bucket


CFN_MAX_OUTPUTS = 50


def create_s3_template(settings):
    """
    Function to create the root S3 template.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    mono_template = False
    if not keyisset(RES_KEY, settings.compose_content):
        return None
    xresources = settings.compose_content[RES_KEY]
    new_buckets = [
        xresources[bucket_name]
        for bucket_name in xresources
        if xresources[bucket_name].properties
    ]
    if not new_buckets:
        LOG.info("There are no buckets to create.")
        return None

    if len(list(new_buckets)) <= CFN_MAX_OUTPUTS:
        mono_template = True

    template = build_template(f"S3 root by ECS ComposeX for {settings.name}")
    for bucket in new_buckets:
        bucket = generate_bucket(bucket, settings)
        if bucket:
            values = [
                (S3_BUCKET_ARN, S3_BUCKET_ARN.title, GetAtt(bucket, "Arn")),
                (S3_BUCKET_NAME, S3_BUCKET_NAME.title, Ref(bucket)),
            ]
            outputs = ComposeXOutput(bucket, values, True)
            if mono_template:
                template.add_resource(bucket)
                template.add_output(outputs.outputs)
            elif not mono_template:
                bucket_template = build_template(
                    f"Template for DynamoDB bucket {bucket.title}"
                )
                bucket_template.add_resource(bucket)
                bucket_template.add_output(outputs.outputs)
                bucket_stack = ComposeXStack(
                    bucket.logical_name, stack_template=bucket_template
                )
                template.add_resource(bucket_stack)
    return template


class Bucket(XResource):
    """
    Class for S3 bucket.
    """


class XStack(ComposeXStack):
    """
    Class to handle S3 buckets
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Bucket, RES_KEY)
        stack_template = create_s3_template(settings)
        if stack_template:
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
