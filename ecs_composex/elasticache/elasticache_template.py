#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to create the ElasticCache Cluster and nodes
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_STACK_NAME, GetAtt, Ref, Sub, Tags
from troposphere.ec2 import SecurityGroup
from troposphere.elasticache import (
    CacheCluster,
    ParameterGroup,
    ReplicationGroup,
    SubnetGroup,
)

from ecs_composex.common import LOG, build_template
from ecs_composex.resources_import import import_record_properties
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID


def init_root_template():
    return build_template("Root stack for ElasticCache", [VPC_ID, STORAGE_SUBNETS])


def create_replication_group(cluster):
    """
    Function to add the replication group from properties

    :param ecs_composex.elasticache.elasticache_stack.CacheCluster cluster:
    :return:
    """
    if (
        not cluster.cfn_resource
        and isinstance(cluster.cfn_resource, CacheCluster)
        and cluster.cfn_resource.Engine == "redis"
    ):
        raise ValueError("Replication group can only be set for a Redis cache cluster.")

    to_del = ["CacheSecurityGroupNames", "PreferredCacheClusterAZs"]
    props = import_record_properties(
        cluster.parameters["ReplicationGroup"], ReplicationGroup
    )
    for prop_to_del in to_del:
        if keyisset(prop_to_del, props):
            del props[prop_to_del]
    if not (
        keyisset("NumCacheClusters", props)
        or keyisset("NumNodeGroups", props)
        or keyisset("ReplicasPerNodeGroup", props)
    ):
        props["PrimaryClusterId"] = Ref(cluster.cfn_resource)
    props["SecurityGroupIds"] = [GetAtt(cluster.db_sg, "GroupId")]
    if cluster.parameter_group:
        props["CacheParameterGroupName"] = Ref(cluster.parameter_group)
    group = ReplicationGroup(f"{cluster.logical_name}ReplicationGroup", **props)
    return group


def create_parameter_group(cluster, definition):
    """
    Function to add the parameter group

    :param ecs_composex.elasticache.elasticache_stack.CacheCluster cluster:
    :param dict definition:
    :return: The parameter group
    :rtype: troposphere.elasticache.ParameterGroup
    """
    props = import_record_properties(definition, ParameterGroup)
    cluster.parameter_group = ParameterGroup(
        f"{cluster.logical_name}ParameterGroup", **props
    )


def determine_resource_type(name, properties):
    """
    Function to determine if the properties are the ones of a DB Cluster or DB Instance.
    By default it will assume Cluster if cannot conclude that it is a DB Instance

    :param str name:
    :param dict properties:
    :return:
    """
    if all(
        property_name in CacheCluster.props.keys()
        for property_name in properties.keys()
    ):
        LOG.info(f"Identified {name} to be {CacheCluster.resource_type}")
        return CacheCluster
    elif all(
        property_name in ReplicationGroup.props.keys()
        for property_name in properties.keys()
    ):
        LOG.info(f"Identified {name} to be {ReplicationGroup.resource_type}")
        return ReplicationGroup
    LOG.error(
        "From the properties defined, we cannot determine whether this is a RDS Cluster or RDS Instance."
        " Setting to Cluster"
    )
    return None


def handle_security_groups(cluster, props, resource_class):
    """
    Function to handle security groups properties and assignment.

    :param ecs_composex.elasticache.elasticache_stack.CacheCluster cluster:
    :param dict props:
    :param resource_class:
    :raises: TypeError
    """
    if resource_class is CacheCluster:
        key = "VpcSecurityGroupIds"
    elif resource_class is ReplicationGroup:
        key = "SecurityGroupIds"
    else:
        raise TypeError(
            "resource_class must be one of",
            [CacheCluster, ReplicationGroup],
            "Got",
            type(resource_class),
        )

    if keyisset(key, props) and not isinstance(props[key], list):
        raise TypeError(f"{key} must be a list. Got", type(props[key]))
    elif keyisset(key, props):
        props[key].append(GetAtt(cluster.db_sg, "GroupId"))
    else:
        props[key] = [GetAtt(cluster.db_sg, "GroupId")]


def create_cluster_from_properties(cluster, template):
    """
    Function to create the Elastic Cache Cluster from properties

    :param ecs_composex.elasticache.elasticache_stack.CacheCluster cluster:
    :param troposphere.Template template:
    :return:
    """
    resource_class = determine_resource_type(cluster.name, cluster.properties)
    props = import_record_properties(cluster.properties, resource_class)
    props["CacheSubnetGroupName"] = Ref(cluster.db_subnet_group)
    handle_security_groups(cluster, props, resource_class)
    default_tags = Tags(Name=cluster.logical_name, ComposeName=cluster.name)
    if keyisset("Tags", props):
        props["Tags"] += default_tags
    else:
        props["Tags"] = default_tags
    if cluster.parameters and keyisset("ParameterGroup", cluster.parameters):
        create_parameter_group(cluster, cluster.parameters["ParameterGroup"])
        template.add_resource(cluster.parameter_group)
        props["CacheParameterGroupName"] = Ref(cluster.parameter_group)
    cluster.cfn_resource = resource_class(cluster.logical_name, **props)
    template.add_resource(cluster.cfn_resource)


def create_cluster_from_parameters(cluster, template):
    """
    Function to create the Cluster from the MacroParameters

    :param ecs_composex.elasticache.elasticache_stack.CacheCluster cluster:
    :param template:
    :return:
    """
    required_keys = ["Engine", "EngineVersion"]
    if not cluster.properties and not all(
        key in required_keys for key in cluster.parameters
    ):
        raise KeyError(
            "When using MacroParameters only, you must specify at least", required_keys
        )
    props = {
        "CacheNodeType": "cache.t3.small"
        if not keyisset("CacheNodeType", cluster.parameters)
        else cluster.parameters["CacheNodeType"],
        "Engine": cluster.parameters["Engine"],
        "EngineVersion": cluster.parameters["EngineVersion"],
        "NumCacheNodes": 1,
        "VpcSecurityGroupIds": [GetAtt(cluster.db_sg, "GroupId")],
        "CacheSubnetGroupName": Ref(cluster.db_subnet_group),
        "Tags": Tags(Name=cluster.logical_name, ComposeName=cluster.name),
    }
    if keyisset("ParameterGroup", cluster.parameters):
        create_parameter_group(cluster, cluster.parameters["ParameterGroup"])
        template.add_resource(cluster.parameter_group)
    cluster.cfn_resource = CacheCluster(cluster.logical_name, **props)
    template.add_resource(cluster.cfn_resource)


def create_root_template(new_resources):
    """
    Function to create the root template and add the new resources to it.

    :param list<ecs_composex.elasticache.elasticache_stack.CacheCluster> new_resources:
    :return: the root template for ElasticCache
    :rtype: troposphere.Template
    """

    root_template = init_root_template()
    for resource in new_resources:
        resource.db_subnet_group = SubnetGroup(
            f"{resource.logical_name}SubnetGroup",
            Description="ElasticCacheSubnetGroup",
            SubnetIds=Ref(STORAGE_SUBNETS)
            if not resource.subnets_override
            else Ref(resource.subnets_override),
        )

        resource.db_sg = SecurityGroup(
            f"{resource.logical_name}Sg",
            GroupDescription=Sub(f"SG for docdb-{resource.logical_name}"),
            GroupName=Sub(f"${{{AWS_STACK_NAME}}}.elasticache.{resource.logical_name}"),
            VpcId=Ref(VPC_ID),
        )
        root_template.add_resource(resource.db_sg)
        root_template.add_resource(resource.db_subnet_group)
        if resource.properties:
            create_cluster_from_properties(resource, root_template)
        elif resource.parameters and not resource.properties:
            create_cluster_from_parameters(resource, root_template)

        if isinstance(resource.cfn_resource, CacheCluster):
            if resource.cfn_resource.Engine == "memcached":
                resource.init_memcached_outputs()
                resource.add_memcahed_config(root_template)
            elif resource.cfn_resource.Engine == "redis":
                resource.init_redis_outputs()
                resource.add_redis_config(root_template)
        elif isinstance(resource.cfn_resource, ReplicationGroup):
            resource.init_redis_replica_outputs()
            resource.add_redis_replica_config(root_template)
        resource.generate_outputs()
        root_template.add_output(resource.outputs)
    return root_template
