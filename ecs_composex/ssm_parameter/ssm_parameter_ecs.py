#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage IAM policies to grant access to ECS Services to DynamodbTables
"""

from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)
from ecs_composex.ssm_parameter.ssm_parameter_aws import lookup_param_config
from ecs_composex.ssm_parameter.ssm_params import RES_KEY, SSM_PARAM_ARN, SSM_PARAM_NAME


def create_ssm_param_mappings(mapping, resources, settings):
    """
    Function to create the resource mapping for SQS Queues.

    :param dict mapping:
    :param list[ecs_composex.ssm_parameter.ssm_parameter_stack.SsmParameter] resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for res in resources:
        res_config = lookup_param_config(res.lookup, settings.session)
        res.mappings = res_config
        mapping.update({res.logical_name: res.mappings})


def ssm_parameter_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SSM Parameters settings to ECS Services
    :return:
    """
    new_resources = [
        resources[res_name]
        for res_name in resources
        if not resources[res_name].lookup and not resources[res_name].use
    ]
    lookup_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].lookup
        and not resources[res_name].properties
        and not resources[res_name].use
    ]
    for new_res in new_resources:
        handle_resource_to_services(
            new_res,
            services_stack,
            res_root_stack,
            settings,
            SSM_PARAM_ARN,
            [SSM_PARAM_NAME],
            nested=False,
        )
    for resource in lookup_resources:
        handle_lookup_resource(
            settings.mappings[RES_KEY],
            resource.mapping_key,
            resource,
            SSM_PARAM_ARN,
            [SSM_PARAM_NAME],
        )
