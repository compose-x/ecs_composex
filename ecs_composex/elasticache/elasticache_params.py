#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Parameters for ES Cluster
"""

from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

CLUSTER_NAME_T = "ClusterName"
CLUSTER_NAME = Parameter(CLUSTER_NAME_T, Type="String")

CLUSTER_SG_T = "GroupId"
CLUSTER_SG = Parameter(CLUSTER_SG_T, return_value="GroupId", Type=SG_ID_TYPE)

CLUSTER_PORT_T = "Port"
CLUSTER_PORT = Parameter(
    CLUSTER_PORT_T, Type="Number", MinValue=1, MaxValue=((2 ** 16) - 1)
)

CLUSTER_MEMCACHED_ADDRESS_T = "ClusterConfigAddress"
CLUSTER_MEMCACHED_ADDRESS = Parameter(
    CLUSTER_MEMCACHED_ADDRESS_T,
    return_value="ConfigurationEndpoint.Address",
    Type="String",
)

CLUSTER_REDIS_ADDRESS_T = "RedisEndpointAddress"
CLUSTER_REDIS_ADDRESS = Parameter(
    CLUSTER_REDIS_ADDRESS_T, return_value="RedisEndpoint.Address", Type="String"
)

CLUSTER_REDIS_PORT_T = "RedisEndpointPort"
CLUSTER_REDIS_PORT = Parameter(
    CLUSTER_REDIS_PORT_T,
    return_value="RedisEndpoint.Port",
    Type="Number",
    MinValue=1,
    MaxValue=(pow(2, 16) - 1),
)

CLUSTER_MEMCACHED_PORT_T = "ClusterConfigPort"
CLUSTER_MEMCACHED_PORT = Parameter(
    CLUSTER_MEMCACHED_PORT_T,
    return_value="ConfigurationEndpoint.Port",
    Type="Number",
    MinValue=1,
    MaxValue=(pow(2, 16) - 1),
)

REPLICA_PRIMARY_ADDRESS_T = "PrimaryEndPointAddress"
REPLICA_PRIMARY_ADDRESS = Parameter(
    REPLICA_PRIMARY_ADDRESS_T,
    return_value="PrimaryEndPoint.Address",
    Type="String",
)

REPLICA_PRIMARY_PORT_T = "PrimaryEndPointPort"
REPLICA_PRIMARY_PORT = Parameter(
    REPLICA_PRIMARY_PORT_T,
    return_value="PrimaryEndPoint.Port",
    Type="String",
)

REPLICA_READ_ENDPOINT_ADDRESSES_T = "ReadEndPointAddresses"
REPLICA_READ_ENDPOINT_ADDRESSES = Parameter(
    REPLICA_READ_ENDPOINT_ADDRESSES_T,
    return_value="ReadEndPoint.Addresses",
    Type="String",
)

REPLICA_READ_ENDPOINT_PORTS_T = "ReadEndPointPorts"
REPLICA_READ_ENDPOINT_PORTS = Parameter(
    REPLICA_READ_ENDPOINT_PORTS_T,
    return_value="ReadEndPoint.Ports",
    Type="String",
)

REPLICA_READ_ENDPOINT_ADDRESSES_LIST_T = "ReadEndPointAddressesList"
REPLICA_READ_ENDPOINT_ADDRESSES_LIST = Parameter(
    REPLICA_READ_ENDPOINT_ADDRESSES_LIST_T,
    return_value="ReadEndPoint.Addresses.List",
    Type="String",
)

REPLICA_READ_ENDPOINT_PORTS_LIST_T = "ReadEndPointPortsList"
REPLICA_READ_ENDPOINT_PORTS_LIST = Parameter(
    REPLICA_READ_ENDPOINT_PORTS_LIST_T,
    return_value="ReadEndPoint.Ports.List",
    Type="String",
)

CLUSTER_CONFIG_T = "ClusterConfig"
CLUSTER_CONFIG = Parameter(CLUSTER_CONFIG_T, Type="AWS::SSM::Parameter::Value<String>")
