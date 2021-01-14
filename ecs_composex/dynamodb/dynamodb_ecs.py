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
Module to manage IAM policies to grant access to ECS Services to DynamodbTables
"""

from ecs_composex.dynamodb.dynamodb_aws import lookup_dynamodb_config
from ecs_composex.resource_settings import (
    handle_resource_to_services,
    handle_lookup_resource,
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
        handle_resource_to_services(new_res, services_stack, res_root_stack, settings)
    for resource in lookup_resources:
        handle_lookup_resource(resources_mappings, "dynamodb", resource)
