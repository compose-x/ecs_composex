#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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
Module to apply SNS settings onto ECS Services
"""

from ecs_composex.common import LOG
from ecs_composex.resource_settings import (
    handle_resource_to_services,
    handle_lookup_resource,
)
from ecs_composex.sns.sns_stack import Topic as XTopic
from ecs_composex.sns.sns_aws import lookup_topic_config


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
            new_res, services_stack, res_root_stack, settings, False
        )
    create_sns_mappings(mappings, lookup_resources, settings)
    for lookup_resource in lookup_resources:
        handle_lookup_resource(mappings, "sns", lookup_resource)
