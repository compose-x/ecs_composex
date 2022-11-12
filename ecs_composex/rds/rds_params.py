# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
ecs_composex.rds parameters.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

DB_SECRET_POLICY_NAME = "RdsDbPolicy"
DB_SECRET_T = "DBSecret"
PARAMETER_GROUP_T = "DBParametersGroup"
CLUSTER_PARAMETER_GROUP_T = "DBClusterParametersGroup"


DB_SG_T = "DBSecurityGroup"
DB_SG = Parameter(DB_SG_T, return_value="GroupId", Type=SG_ID_TYPE)

DB_ENGINE_NAME_T = "Engine"
DB_ENGINE_NAME = Parameter(DB_ENGINE_NAME_T, Type="String")

DB_ENGINE_VERSION_T = "EngineVersion"
DB_ENGINE_VERSION = Parameter(DB_ENGINE_VERSION_T, Type="String")

DB_INSTANCE_CLASS_T = "DatabaseInstanceSize"
DB_INSTANCE_CLASS = Parameter(
    DB_INSTANCE_CLASS_T, Type="String", Default="db.t3.medium"
)

DBS_SUBNET_GROUP_T = "DatabasesSubnetGroup"
DBS_SUBNET_GROUP = Parameter(DBS_SUBNET_GROUP_T, Type="String", Default="self")

DB_NAME_T = "DatabaseName"
DB_NAME = Parameter(DB_NAME_T, Type="String", AllowedPattern=r"([a-zA-Z0-9-]+)")

DB_SNAPSHOT_ID_T = "RdsSnapshotId"
DB_SNAPSHOT_ID = Parameter(DB_SNAPSHOT_ID_T, Type="String", Default="none")

DB_PASSWORD_LENGTH_T = "DatabasePasswordLength"
DB_PASSWORD_LENGTH = Parameter(
    DB_PASSWORD_LENGTH_T, Type="Number", MinValue=8, MaxValue=32, Default=16
)

DB_USERNAME_T = "DatabaseUsername"
DB_USERNAME = Parameter(
    DB_USERNAME_T, Type="String", MinLength=3, MaxLength=16, Default="dbadmin"
)

DB_STORAGE_CAPACITY_T = "DatabaseStorageCapacity"
DB_STORAGE_CAPACITY = Parameter(
    DB_STORAGE_CAPACITY_T,
    Type="Number",
    MinValue=8,
    MaxValue=(18 * 1024),
    Default=8,
)

DB_STORAGE_TYPE_T = "DatabaseStorageType"
DB_STORAGE_TYPE = Parameter(
    DB_STORAGE_TYPE_T,
    Type="String",
    AllowedValues=["gp2", "io1"],
    Default="gp2",
)

DB_EXPORT_PREFIX_T = "RdsDb"
DB_EXPORT_PORT_T = "Endpoint.Port"

DB_EXPORT_SG_ID_T = "RdsSecurityGroup"

DB_ENDPOINT_PORT_T = "EndpointPort"
DB_ENDPOINT_ADDRESS_T = "EndpointAddress"
DB_RO_ENDPOINT_ADDRESS_T = "ReadEndpointAddress"

DB_ENDPOINT_ADDRESS = Parameter(
    DB_ENDPOINT_ADDRESS_T, return_value="Endpoint.Address", Type="String"
)
DB_RO_ENDPOINT_ADDRESS = Parameter(
    DB_RO_ENDPOINT_ADDRESS_T, return_value="ReadEndpoint.Address", Type="String"
)
DB_ENDPOINT_PORT = Parameter(
    DB_ENDPOINT_PORT_T, return_value="Endpoint.Port", Type="Number"
)

DB_SECRET_ARN = Parameter(DB_SECRET_T, Type="String")

DB_CLUSTER_ARN_T = "DBClusterArn"
DB_CLUSTER_ARN = Parameter(DB_CLUSTER_ARN_T, return_value="DBClusterArn", Type="String")

DB_INSTANCE_ARN_T = "DBInstanceArn"
DB_INSTANCE_ARN = Parameter(
    DB_INSTANCE_ARN_T, return_value="DBInstanceArn", Type="String"
)

DB_CLUSTER_NAME_T = "DBCluster"
DB_CLUSTER_NAME = Parameter(DB_CLUSTER_NAME_T, Type="String")
