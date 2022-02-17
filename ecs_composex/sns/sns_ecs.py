#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to apply SNS settings onto ECS Services
"""

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.resource_settings import (
    handle_lookup_resource,
    handle_resource_to_services,
)
from ecs_composex.sns.sns_params import TOPIC_ARN
from ecs_composex.sns.sns_stack import Topic as XTopic


def sns_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    if not keyisset(XTopic.keyword, resources):
        return
    for resource_name, resource in resources[XTopic.keyword].items():
        LOG.info(f"{resource.module_name}.{resource_name} - Linking to services")
        if resource.cfn_resource and not resource.mappings:
            handle_resource_to_services(
                resource,
                services_stack,
                res_root_stack,
                settings,
                TOPIC_ARN,
                parameters=list(resource.attributes_outputs.keys()),
            )
        elif resource.mappings and not resource.cfn_resource:
            handle_lookup_resource(settings, resource, TOPIC_ARN)
