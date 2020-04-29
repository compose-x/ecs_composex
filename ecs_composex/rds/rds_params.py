# -*- coding: utf-8 -*-
"""
ecs_composex.rds parameters
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
