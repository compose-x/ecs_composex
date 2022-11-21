# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle Linking ECS tasks and the elastic cache clusters
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from .elasticache_stack import CacheCluster

from troposphere import FindInMap, Select

from ecs_composex.common.logging import LOG
from ecs_composex.elasticache.elasticache_aws import lookup_cluster_resource
from ecs_composex.elasticache.elasticache_params import (
    CLUSTER_SG,
    MAPPINGS_KEY,
    RES_KEY,
)
from ecs_composex.rds_resources_settings import (
    add_security_group_ingress,
    handle_new_tcp_resource,
)


def link_cluster_to_service(
    cluster: CacheCluster, cluster_mappings: dict, mapping_name: str
):
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


def create_lookup_mappings(
    mappings: dict, lookup_resources: list[CacheCluster], settings: ComposeXSettings
):
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
        resource.mappings = resource_config


def elasticache_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map new and lookup resources to ECS Services

    :param dict resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for resource_name, resource in resources.items():
        LOG.info(f"{resource.module.res_key}.{resource_name} - Linking to services")
        if not resource.mappings and resource.cfn_resource:
            handle_new_tcp_resource(
                resource,
                port_parameter=resource.port_attr,
                sg_parameter=CLUSTER_SG,
                settings=settings,
            )
        elif resource.mappings and not resource.cfn_resource:
            link_cluster_to_service(
                resource, settings.mappings[RES_KEY], mapping_name=MAPPINGS_KEY
            )
