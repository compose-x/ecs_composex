#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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
Module to create the ElasticCache Cluster and nodes
"""

from troposphere import Ref, Sub, GetAtt, Tags
from troposphere import AWS_NO_VALUE, AWS_REGION, AWS_STACK_NAME
from troposphere.ec2 import SecurityGroup

from troposphere.elasticache import (
    CacheCluster,
    ReplicationGroup,
    SubnetGroup,
    ParameterGroup,
)

from ecs_composex.resources_import import import_record_properties
from ecs_composex.common import build_template, add_parameters, keyisset, keypresent
from ecs_composex.vpc.vpc_params import VPC_ID, STORAGE_SUBNETS


def init_root_template():
    return build_template("Root stack for ElasticCache", [VPC_ID, STORAGE_SUBNETS])


def create_replication_group(cluster):
    """
    Function to add the replication group from properties

    :param ecs_composex.elastic_cache.elastic_cache_stack.CacheCluster cluster:
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

    :param ecs_composex.elastic_cache.elastic_cache_stack.CacheCluster cluster:
    :param dict definition:
    :return: The parameter group
    :rtype: troposphere.elasticache.ParameterGroup
    """
    props = import_record_properties(definition, ParameterGroup)
    cluster.parameter_group = ParameterGroup(
        f"{cluster.logical_name}ParameterGroup", **props
    )


def create_cluster_from_properties(cluster, template, subnet_group):
    """
    Function to create the Elastic Cache Cluster from properties

    :param ecs_composex.elastic_cache.elastic_cache_stack.CacheCluster cluster:
    :param troposphere.Template template:
    :param troposphere.elastic_cache.SubnetGroup subnet_group:
    :return:
    """
    props = import_record_properties(cluster.properties, CacheCluster)
    props["VpcSecurityGroupIds"] = [GetAtt(cluster.db_sg, "GroupId")]
    props["CacheSubnetGroupName"] = Ref(subnet_group)
    if keyisset("Tags", props):
        props["Tags"] += Tags(Name=cluster.logical_name, ComposeName=cluster.name)
    if cluster.parameters and keyisset("ParameterGroup", cluster.parameters):
        create_parameter_group(cluster, cluster.parameters["ParameterGroup"])
        template.add_resource(cluster.parameter_group)
        props["CacheParameterGroupName"] = Ref(cluster.parameter_group)
    cluster.cfn_resource = CacheCluster(cluster.logical_name, **props)
    template.add_resource(cluster.cfn_resource)
    if cluster.parameters and keyisset("ReplicationGroup", cluster.parameters):
        replica_group = create_replication_group(cluster)
        template.add_resource(replica_group)


def create_cluster_from_parameters(cluster, template, subnet_group):
    """
    Function to create the Cluster from the MacroParameters

    :param ecs_composex.elastic_cache.elastic_cache_stack.CacheCluster cluster:
    :param template:
    :param subnet_group:
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
    }
    if keyisset("ParameterGroup", cluster.parameters):
        create_parameter_group(cluster, cluster.parameters["ParameterGroup"])
        template.add_resource(cluster.parameter_group)
    cluster.cfn_resource = CacheCluster(cluster.logical_name, **props)
    template.add_resource(cluster.cfn_resource)


def create_root_template(new_resources):
    """
    Function to create the root template and add the new resources to it.

    :param list<ecs_composex.elastic_cache.elastic_cache_stack.CacheCluster> new_resources:
    :param settings:
    :return: the root template for ElasticCache
    :rtype: troposphere.Template
    """

    root_template = init_root_template()
    subnet_group = root_template.add_resource(
        SubnetGroup(
            f"ElasticCacheSubnetGroup",
            Description="ElasticCacheSubnetGroup",
            SubnetIds=Ref(STORAGE_SUBNETS),
        )
    )
    for resource in new_resources:
        resource.db_sg = SecurityGroup(
            f"{resource.logical_name}Sg",
            GroupDescription=Sub(f"SG for docdb-{resource.logical_name}"),
            GroupName=Sub(
                f"${{{AWS_STACK_NAME}}}.elasticcache.{resource.logical_name}"
            ),
            VpcId=Ref(VPC_ID),
        )
        root_template.add_resource(resource.db_sg)
        if resource.properties:
            create_cluster_from_properties(resource, root_template, subnet_group)
        elif resource.parameters and not resource.properties:
            create_cluster_from_parameters(resource, root_template, subnet_group)
        resource.init_outputs()
        resource.generate_outputs()
        root_template.add_output(resource.outputs)
    return root_template
