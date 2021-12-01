#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage IAM policies to grant access to ECS Services to DynamodbTables
"""

from ecs_composex.dynamodb.dynamodb_params import (
    MAPPINGS_KEY,
    RES_KEY,
    TABLE_ARN,
    TABLE_NAME,
)
from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)


def dynamodb_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    new_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].cfn_resource
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].mappings
    ]
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
            settings.mappings[RES_KEY], MAPPINGS_KEY, resource, TABLE_ARN, [TABLE_NAME]
        )
