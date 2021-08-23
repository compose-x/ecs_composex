﻿#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to control S3 stack
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import MAX_OUTPUTS, GetAtt, Ref

from ecs_composex.common import build_template
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.s3.s3_ecs import define_bucket_mappings
from ecs_composex.s3.s3_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    S3_BUCKET_ARN,
    S3_BUCKET_DOMAIN_NAME,
    S3_BUCKET_NAME,
)
from ecs_composex.s3.s3_template import generate_bucket

COMPOSEX_MAX_OUTPUTS = MAX_OUTPUTS - 10


def create_s3_template(new_buckets, template):
    """
    Function to create the root S3 template.

    :param list new_buckets:
    :param troposphere.Template template:
    :return:
    """
    mono_template = False
    if len(list(new_buckets)) <= COMPOSEX_MAX_OUTPUTS:
        mono_template = True

    for bucket in new_buckets:
        bucket = generate_bucket(bucket)
        if bucket and bucket.cfn_resource:
            bucket.init_outputs()
            bucket.generate_outputs()
            if mono_template:
                template.add_resource(bucket.cfn_resource)
                template.add_output(bucket.outputs)
            elif not mono_template:
                bucket_template = build_template(
                    f"Template for S3 Bucket {bucket.title}"
                )
                bucket_template.add_resource(bucket.cfn_resource)
                bucket_template.add_output(bucket.outputs)
                bucket_stack = ComposeXStack(
                    bucket.logical_name, stack_template=bucket_template
                )
                template.add_resource(bucket_stack)
    return template


class Bucket(XResource):
    """
    Class for S3 bucket.
    """

    def init_outputs(self):
        self.output_properties = {
            S3_BUCKET_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            S3_BUCKET_ARN: (
                f"{self.logical_name}{S3_BUCKET_ARN.title}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_ARN.return_value,
            ),
            S3_BUCKET_DOMAIN_NAME: (
                f"{self.logical_name}{S3_BUCKET_DOMAIN_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_DOMAIN_NAME.return_value,
                None,
            ),
        }


class XStack(ComposeXStack):
    """
    Class to handle S3 buckets
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Bucket, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, True)
        if new_resources:
            stack_template = build_template(
                f"S3 root by ECS ComposeX for {settings.name}"
            )
            super().__init__(title, stack_template, **kwargs)
            create_s3_template(new_resources, stack_template)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            define_bucket_mappings(
                settings.mappings[RES_KEY], lookup_resources, use_resources, settings
            )
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
