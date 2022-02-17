#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to add permissions etc. for services to kinesis streams
"""

from ecs_composex.common import LOG
from ecs_composex.kinesis.kinesis_params import STREAM_ARN, STREAM_ID
from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)


def kinesis_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply Kinesis settings to ECS Services
    :return:
    """
    for resource_name, resource in resources.items():
        LOG.info(f"{resource.module_name}.{resource_name} - Linking to services")
        if not resource.mappings and resource.cfn_resource:
            handle_resource_to_services(
                resource,
                services_stack,
                res_root_stack,
                settings,
                STREAM_ARN,
                [STREAM_ID],
            )
        elif resource.mappings and not resource.cfn_resource:
            handle_lookup_resource(
                settings,
                resource,
                STREAM_ARN,
            )
