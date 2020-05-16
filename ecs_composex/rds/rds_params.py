# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from troposphere import Parameter

RES_KEY = "x-rds"
DB_SECRET_POLICY_NAME = "RdsDbPolicy"

DB_SG_T = "DatabaseSecurityGroup"

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
DB_EXPORT_PORT_T = "RdsPort"
DB_EXPORT_SECRET_ARN_T = "RdsSecretArn"
DB_EXPORT_SG_ID_T = "RdsDbSecurityGroup"
