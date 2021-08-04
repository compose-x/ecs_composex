#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to scan and find the DB and Secret for Lookup of x-rds
"""

import re

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.elasticache import elasticache_params


def get_cluster_config(resource, cluster_name, session):
    client = session.client("elasticache")
    try:
        cluster_r = client.describe_cache_clusters(
            CacheClusterId=cluster_name,
            ShowCacheClustersNotInReplicationGroups=True,
            ShowCacheNodeInfo=True,
        )
        cluster = cluster_r["CacheClusters"][0]
        if cluster["Engine"] == "memcached":
            resource.port_attr = elasticache_params.CLUSTER_MEMCACHED_PORT
            return {
                elasticache_params.CLUSTER_MEMCACHED_ADDRESS.title: cluster[
                    "ConfigurationEndpoint"
                ]["Address"],
                elasticache_params.CLUSTER_MEMCACHED_PORT.title: cluster[
                    "ConfigurationEndpoint"
                ]["Port"],
                elasticache_params.CLUSTER_SG.title: [
                    cluster["SecurityGroups"][0]["SecurityGroupId"]
                ],
            }
        elif cluster["Engine"] == "redis":
            if keyisset("ReplicationGroupId", cluster):
                raise LookupError(
                    "The Cluster identified is part of a replication group."
                )
            resource.port_attr = elasticache_params.CLUSTER_REDIS_PORT
            return {
                elasticache_params.CLUSTER_REDIS_PORT.title: cluster["CacheNodes"][0][
                    "Endpoint"
                ]["Port"],
                elasticache_params.CLUSTER_REDIS_ADDRESS.title: cluster["CacheNodes"][
                    0
                ]["Endpoint"]["Address"],
                elasticache_params.CLUSTER_SG.title: [
                    cluster["SecurityGroups"][0]["SecurityGroupId"]
                ],
            }
    except client.exceptions.CacheClusterNotFoundFault:
        LOG.error(f"Could not find the configurations for cluster {cluster_name}")


def get_replica_group_config(resource, cluster_name, session):
    client = session.client("elasticache")
    try:
        cluster_r = client.describe_replication_groups(ReplicationGroupId=cluster_name)
        cluster = cluster_r["ReplicationGroups"][0]
        node_r = client.describe_cache_clusters(
            CacheClusterId=cluster["MemberClusters"][0]
        )
        sg_id = node_r["CacheClusters"][0]["SecurityGroups"][0]["SecurityGroupId"]
        resource.port_attr = elasticache_params.REPLICA_PRIMARY_PORT
        return {
            elasticache_params.REPLICA_PRIMARY_ADDRESS.title: cluster["NodeGroups"][0][
                "PrimaryEndpoint"
            ]["Address"],
            elasticache_params.REPLICA_PRIMARY_PORT.title: cluster["NodeGroups"][0][
                "PrimaryEndpoint"
            ]["Port"],
            elasticache_params.REPLICA_READ_ENDPOINT_ADDRESSES.title: [
                cluster["NodeGroups"][0]["ReaderEndpoint"]["Address"]
            ],
            elasticache_params.REPLICA_READ_ENDPOINT_PORTS.title: [
                cluster["NodeGroups"][0]["ReaderEndpoint"]["Port"]
            ],
            elasticache_params.CLUSTER_SG.title: [sg_id],
        }
    except client.exceptions.ReplicationGroupNotFoundFault as error:
        LOG.error(f"Could not fetch information about {cluster_name}")
        LOG.error(error)
        return None


def return_cluster_config(resource, cluster_arn, session):
    """
    Function to retrieve the DB information we need for services integration

    :param ecs_composex.elasticache.elasticache_stack.CacheCluster resource:
    :param cluster_arn:
    :param session:
    :type cluster_arn: str
    :type session: boto3.session.Session
    :return: the DB details
    """

    if isinstance(cluster_arn, str):
        cluster_name = re.sub(
            r"(?:^arn:aws(?:-[a-z]+)?:elasticache:[\w-]+:[0-9]{12}:cluster:)",
            "",
            cluster_arn,
        )
        return get_cluster_config(resource, cluster_name, session)
    elif isinstance(cluster_arn, list):
        if not re.match(
            r"(?:^arn:aws(?:-[a-z]+)?:elasticache:[\w-]+:[0-9]{12}:cluster:)([\S]+)(?:-[0-9]+)$",
            cluster_arn[0],
        ).groups():
            raise ValueError("Could not match the ARN to a specific Replica Group")
        cluster_name = re.match(
            r"(?:^arn:aws(?:-[a-z]+)?:elasticache:[\w-]+:[0-9]{12}:cluster:)([\S]+)(?:-[0-9]+)$",
            cluster_arn[0],
        ).groups()[0]
        return get_replica_group_config(resource, cluster_name, session)


def lookup_cluster_resource(resource, session):
    """
    Function to find the DB in AWS account

    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    elasticache_types = {
        "elasticache:cluster": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:elasticache:[\w-]+:[0-9]{12}:cluster:)([\S]+)$"
        }
    }
    res_type = "elasticache:cluster"
    lookup_session = define_lookup_role_from_info(resource.lookup, session)
    cluster_arn = find_aws_resource_arn_from_tags_api(
        resource.lookup,
        lookup_session,
        res_type,
        types=elasticache_types,
        allow_multi=True,
    )
    if not cluster_arn:
        return None
    cluster_config = return_cluster_config(resource, cluster_arn, lookup_session)
    LOG.debug(cluster_config)
    return cluster_config
