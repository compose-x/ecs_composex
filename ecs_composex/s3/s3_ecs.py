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
Functions to pass permissions to Services to access S3 buckets.
"""

from troposphere.s3 import Bucket

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resource_permissions import apply_iam_based_resources
from ecs_composex.resource_settings import (
    generate_resource_envvars,
    generate_resource_permissions,
    validate_lookup_resource,
)
from ecs_composex.s3.s3_aws import lookup_s3_bucket
from ecs_composex.s3.s3_params import S3_BUCKET_NAME
from ecs_composex.s3.s3_perms import generate_s3_permissions


def handle_new_buckets(
    xresources,
    services_families,
    services_stack,
    res_root_stack,
    l_buckets,
    nested=False,
):
    buckets_r = []
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if isinstance(s_resources[resource_name], Bucket):
            buckets_r.append(s_resources[resource_name].title)
        elif issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_buckets(
                xresources,
                services_families,
                services_stack,
                s_resources[resource_name],
                l_buckets,
                nested=True,
            )

    for bucket_name in xresources:
        if bucket_name in buckets_r or NONALPHANUM.sub("", bucket_name) in buckets_r:
            perms = generate_s3_permissions(
                NONALPHANUM.sub("", bucket_name), S3_BUCKET_NAME
            )
            envvars = generate_resource_envvars(
                bucket_name, xresources[bucket_name], S3_BUCKET_NAME
            )
            apply_iam_based_resources(
                xresources[bucket_name],
                services_families,
                services_stack,
                res_root_stack,
                envvars,
                perms,
                nested,
            )
            del l_buckets[bucket_name]


def s3_to_ecs(
    xresources, services_stack, services_families, res_root_stack, settings, **kwargs
):
    """
    Function to handle permissions assignment to ECS services.

    :param xresources: x-sqs queues defined in compose file
    :param ecs_composex.common.stack.ComposeXStack services_stack: services root stack
    :param services_families: services families
    :param ecs_composex.common.stack.ComposeXStack res_root_stack: s3 root stack
    :param ecs_composex.common.settings.ComposeXSettings settings: ComposeX Settings for execution
    :param dict kwargs:
    :return:
    """
    l_buckets = xresources.copy()
    handle_new_buckets(
        xresources, services_families, services_stack, res_root_stack, l_buckets
    )
    for bucket_name in l_buckets:
        bucket = xresources[bucket_name]
        bucket_res_name = NONALPHANUM.sub("", bucket_name)
        validate_lookup_resource(bucket_res_name, bucket, res_root_stack)
        found_resources = lookup_s3_bucket(
            settings.session, tags=bucket["Lookup"]["Tags"]
        )
        if not found_resources:
            LOG.warning(
                f"404 not buckets found with the provided tags was found in definition {bucket_name}."
            )
            continue
        for found_bucket in found_resources:
            bucket.update(found_bucket)
            perms = generate_s3_permissions(
                found_bucket["Name"],
                S3_BUCKET_NAME,
                arn=found_bucket["Arn"],
            )
            envvars = generate_resource_envvars(
                bucket_name,
                xresources[bucket_name],
                S3_BUCKET_NAME,
                arn=found_bucket["Name"],
            )
            apply_iam_based_resources(
                bucket,
                services_families,
                services_stack,
                res_root_stack,
                envvars,
                perms,
            )
