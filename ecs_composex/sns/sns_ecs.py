# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


"""
Module to apply SNS settings onto ECS Services
"""

from ecs_composex.common import LOG
from ecs_composex.resource_settings import (
    handle_resource_to_services,
    handle_lookup_resource,
)
from ecs_composex.sns.sns_aws import lookup_topic_config
from ecs_composex.sns.sns_params import TOPIC_NAME, TOPIC_ARN
from ecs_composex.sns.sns_stack import Topic as XTopic


def create_sns_mappings(mapping, resources, settings):
    for resource in resources:
        resource_config = lookup_topic_config(
            resource.logical_name, resource.lookup, settings.session
        )
        if resource_config:
            mapping.update({resource.logical_name: resource_config})


def sns_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    mappings = {}
    new_resources = [
        resources[XTopic.keyword][resource_name]
        for resource_name in resources[XTopic.keyword]
        if not resources[XTopic.keyword][resource_name].lookup
    ]
    lookup_resources = [
        resources[XTopic.keyword][resource_name]
        for resource_name in resources[XTopic.keyword]
        if resources[XTopic.keyword][resource_name].lookup
    ]
    if new_resources and res_root_stack.title not in services_stack.DependsOn:
        services_stack.DependsOn.append(res_root_stack.title)
        LOG.info(f"Added dependency between services and {res_root_stack.title}")
    for new_res in new_resources:
        handle_resource_to_services(
            new_res, services_stack, res_root_stack, settings, TOPIC_ARN, [TOPIC_NAME]
        )
    create_sns_mappings(mappings, lookup_resources, settings)
    for lookup_resource in lookup_resources:
        handle_lookup_resource(
            mappings, "sns", lookup_resource, TOPIC_ARN, [TOPIC_NAME]
        )
