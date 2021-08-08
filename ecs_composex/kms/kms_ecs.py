#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage IAM policies to grant access to ECS Services to KMS Keys
"""

from ecs_composex.common import LOG
from ecs_composex.kms.kms_aws import lookup_key_config
from ecs_composex.kms.kms_params import KMS_KEY_ARN, KMS_KEY_ID
from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)


def create_kms_mappings(mapping, resources, settings):
    """
    Function to create the resource mapping for SQS Queues.

    :param dict mapping:
    :param list resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for res in resources:
        res_config = lookup_key_config(res.logical_name, res.lookup, settings.session)
        mapping.update({res.logical_name: res_config})


def kms_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    resources_mappings = {}
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].lookup
    ]
    if new_resources and res_root_stack.title not in services_stack.DependsOn:
        services_stack.DependsOn.append(res_root_stack.title)
        LOG.info(f"Added dependency between services and {res_root_stack.title}")
    for new_res in new_resources:
        handle_resource_to_services(
            new_res,
            services_stack,
            res_root_stack,
            settings,
            KMS_KEY_ARN,
            [KMS_KEY_ID],
        )
    create_kms_mappings(resources_mappings, lookup_resources, settings)
    for lookup_res in lookup_resources:
        handle_lookup_resource(
            resources_mappings, "kms", lookup_res, KMS_KEY_ARN, [KMS_KEY_ID]
        )
