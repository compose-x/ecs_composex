#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage IAM policies to grant access to ECS Services to DynamodbTables
"""

from ecs_composex.dynamodb.dynamodb_aws import lookup_dynamodb_config
from ecs_composex.dynamodb.dynamodb_params import TABLE_ARN, TABLE_NAME
from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)


def create_dyndb_mappings(mapping, resources, settings):
    """
    Function to create the resource mapping for SQS Queues.

    :param dict mapping:
    :param list resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for res in resources:
        res_config = lookup_dynamodb_config(res.lookup, settings.session)
        mapping.update({res.logical_name: res_config})


def dynamodb_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    resources_mappings = {}
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].lookup and not resources[res_name].properties
    ]
    create_dyndb_mappings(resources_mappings, lookup_resources, settings)
    for new_res in new_resources:
        handle_resource_to_services(
            new_res,
            services_stack,
            res_root_stack,
            settings,
            TABLE_ARN,
            [TABLE_NAME],
            nested=False,
        )
    for resource in lookup_resources:
        handle_lookup_resource(
            resources_mappings, "dynamodb", resource, TABLE_ARN, [TABLE_NAME]
        )
