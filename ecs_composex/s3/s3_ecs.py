#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Functions to pass permissions to Services to access S3 buckets.
"""

from ecs_composex.common import LOG
from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)
from ecs_composex.s3.s3_params import S3_BUCKET_ARN


def s3_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to handle permissions assignment to ECS services.

    :param dict resources: x-s3 buckets defined in compose file
    :param ecs_composex.common.stack.ComposeXStack services_stack: services root stack
    :param ecs_composex.common.stack.ComposeXStack res_root_stack: s3 root stack
    :param ecs_composex.common.settings.ComposeXSettings settings: ComposeX Settings for execution
    :return:
    """

    for resource_name, resource in resources.items():
        LOG.info(f"{resource.module_name}.{resource_name} - Linking to services")
        if (
            resource.cfn_resource
            and not resource.lookup_properties
            and not resource.mappings
        ):
            handle_resource_to_services(
                resource,
                services_stack,
                res_root_stack,
                settings,
                arn_parameter=S3_BUCKET_ARN,
                parameters=list(resource.attributes_outputs.keys()),
                access_subkeys=["objects", "bucket", "enforceSecureConnection"],
            )
        elif (
            resource.lookup_properties
            and resource.mappings
            and not resource.cfn_resource
        ):
            handle_lookup_resource(
                settings.mappings[resource.mapping_key],
                resource.mapping_key,
                resource,
                arn_parameter=S3_BUCKET_ARN,
                access_subkeys=["objects", "bucket", "enforceSecureConnection"],
            )
