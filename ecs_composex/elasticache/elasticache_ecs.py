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
Module to handle Linking ECS tasks and the elastic cache clusters
"""

from troposphere import FindInMap, Select

from ecs_composex.common import keyisset
from ecs_composex.elasticache.elasticache_aws import lookup_cluster_resource
from ecs_composex.elasticache.elasticache_params import CLUSTER_SG
from ecs_composex.tcp_resources_settings import (
    handle_new_tcp_resource,
    add_security_group_ingress,
)


def link_cluster_to_service(cluster, cluster_mappings, mapping_name):
    """
    Function to go over each service defined in the DB and assign found DB settings to service

    :param ecs_composex.elasticache.elasticache_stack.CacheCluster cluster:
    :param dict cluster_mappings:
    :param str mapping_name:
    :return:
    """
    for target in cluster.families_targets:
        target[0].template.add_mapping(mapping_name, cluster_mappings)
        add_security_group_ingress(
            target[0].stack,
            cluster.logical_name,
            sg_id=Select(
                0, FindInMap(mapping_name, cluster.logical_name, CLUSTER_SG.title)
            ),
            port=FindInMap(mapping_name, cluster.logical_name, cluster.port_attr.title),
        )


def create_lookup_mappings(mappings, lookup_resources, settings):
    """
    Function to build up the Mappings for ElastiCache

    :param mappings:
    :param lookup_resources:
    :param settings:
    :return:
    """
    for resource in lookup_resources:
        resource_config = lookup_cluster_resource(resource, settings.session)
        if not resource_config:
            continue
        mappings[resource.logical_name] = resource_config


def elasticache_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map new and lookup resources to ECS Services

    :param list resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    db_mappings = {}
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].lookup
    ]
    for new_res in new_resources:
        handle_new_tcp_resource(new_res, res_root_stack, new_res.port_attr)
    create_lookup_mappings(db_mappings, lookup_resources, settings)
    for lookup_res in lookup_resources:
        if keyisset(lookup_res.logical_name, db_mappings):
            link_cluster_to_service(lookup_res, db_mappings, mapping_name="ElastiCache")
