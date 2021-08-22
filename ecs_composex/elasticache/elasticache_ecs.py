#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to handle Linking ECS tasks and the elastic cache clusters
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap, Select

from ecs_composex.elasticache.elasticache_aws import lookup_cluster_resource
from ecs_composex.elasticache.elasticache_params import (
    CLUSTER_SG,
    MAPPINGS_KEY,
    RES_KEY,
)
from ecs_composex.tcp_resources_settings import (
    add_security_group_ingress,
    handle_new_tcp_resource,
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
                0,
                FindInMap(mapping_name, cluster.logical_name, CLUSTER_SG.title),
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
    new_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].cfn_resource
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].mappings
    ]
    for new_res in new_resources:
        handle_new_tcp_resource(
            new_res,
            res_root_stack,
            port_parameter=new_res.port_attr,
            sg_parameter=CLUSTER_SG,
        )
    for lookup_res in lookup_resources:
        if keyisset(lookup_res.logical_name, settings.mappings[RES_KEY]):
            link_cluster_to_service(
                lookup_res, settings.mappings[RES_KEY], mapping_name=MAPPINGS_KEY
            )
