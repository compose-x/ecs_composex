# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
ecs_composex.rds parameters.

This is a crucial part as all the titles, marked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from os import path
from ecs_composex.ecs_composex import X_KEY
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"

DB_SECRET_POLICY_NAME = "RdsDbPolicy"
CLUSTER_SUBNET_GROUP = "RdsSubnetGroup"
DB_SECRET_T = "RdsDbSecret"
CLUSTER_T = "AuroraCluster"
DATABASE_T = "RdsDatabase"
PARAMETER_GROUP_T = "RdsParametersGroup"
CLUSTER_PARAMETER_GROUP_T = "RdsClusterParameterGroup"


DB_SG_T = "RdsSg"
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
    DB_STORAGE_CAPACITY_T, Type="Number", MinValue=8, MaxValue=(18 * 1024), Default=8
)

DB_STORAGE_TYPE_T = "DatabaseStorageType"
DB_STORAGE_TYPE = Parameter(
    DB_STORAGE_TYPE_T, Type="String", AllowedValues=["gp2", "io1"], Default="gp2"
)

DB_EXPORT_PREFIX_T = "RdsDb"
DB_EXPORT_PORT_T = "Endpoint.Port"

DB_EXPORT_SG_ID_T = "RdsSecurityGroup"

DB_ENDPOINT_PORT_T = "RDSClusterEndpointPort"
DB_ENDPOINT_ADDRESS_T = "RDSClusterEndpointAddress"
DB_RO_ENDPOINT_ADDRESS_T = "RDSClusterReadEndpointAddress"

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
