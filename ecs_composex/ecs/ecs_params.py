#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Parameters bound to  ecs_composex.ecs
This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it [a-zA-Z0-9]
"""

from troposphere import ImportValue, Ref, Select, Split, Sub

from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, Parameter
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as delim
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

CLUSTER_T = "EcsCluster"
LOG_GROUP_T = "ServicesLogGroup"
SG_T = "ServiceSecurityGroup"
NETWORK_MODE = "awsvpc"
EXEC_ROLE_T = "EcsExecutionRole"
TASK_ROLE_T = "EcsTaskRole"
SERVICE_T = "EcsServiceDefinition"
TASK_T = "EcsTaskDefinition"
RES_KEY = "services"
ECS_TASK_FAMILY_LABEL = "ecs.task.family"
SERVICE_SCALING_TARGET = "ServiceScalingTarget"

LAUNCH_TYPE_T = "EcsLaunchType"
LAUNCH_TYPE = Parameter(
    LAUNCH_TYPE_T,
    Type="String",
    AllowedValues=["EC2", "FARGATE", "CAPACITY_PROVIDERS"],
    Default="FARGATE",
)

FARGATE_VERSION_T = "FargatePlatformVersion"
FARGATE_VERSION = Parameter(
    FARGATE_VERSION_T,
    Type="String",
    AllowedValues=["DEFAULT", "1.4.0", "1.3.0"],
    Default="1.4.0",
)

IS_PUBLIC_T = "ExposeServicePublicly"
IS_PUBLIC = Parameter(IS_PUBLIC_T, AllowedValues=["True", "False"], Type="String")

CLUSTER_NAME_T = "EcsClusterName"
CLUSTER_NAME = Parameter(
    CLUSTER_NAME_T,
    Type="String",
    AllowedPattern=r"[a-zA-Z0-9-]+",
    Default="default",
)

CREATE_CLUSTER_PT = "CreateEcsCluster"
CREATE_CLUSTER = Parameter(
    CREATE_CLUSTER_PT,
    Type="String",
    AllowedValues=["True", "False"],
    Default="True",
)

SERVICE_NAME_T = "MicroServiceName"
SERVICE_NAME = Parameter(SERVICE_NAME_T, Type="String", AllowedPattern=r"[a-zA-Z0-9-]+")

SERVICE_HOSTNAME_T = "MicroserviceHostname"
SERVICE_HOSTNAME = Parameter(
    SERVICE_HOSTNAME_T,
    Type="String",
    Default="default",
    AllowedPattern=r"^[a-z0-9-.]+$",
)

SERVICE_IMAGE_T = "MicroserviceImage"
SERVICE_IMAGE = Parameter(SERVICE_IMAGE_T, Type="String")

SERVICE_COUNT_T = "MicroservicesCount"
SERVICE_COUNT = Parameter(SERVICE_COUNT_T, Type="Number", MinValue=0, Default=0)

ELB_GRACE_PERIOD_T = "ElbGracePeriod"
ELB_GRACE_PERIOD = Parameter(
    ELB_GRACE_PERIOD_T,
    Type="Number",
    MinValue=0,
    Default=300,
    MaxValue=2147483647,
)

ECS_CONTROLLER_T = "EcsServiceDeploymentController"
ECS_CONTROLLER = Parameter(
    ECS_CONTROLLER_T,
    Type="String",
    AllowedValues=["ECS", "CODE_DEPLOY", "EXTERNAL"],
    Default="ECS",
)

CREATE_LOG_GROUP_T = "CreateLogGroup"
CREATE_LOG_GROUP = Parameter(
    CREATE_LOG_GROUP_T,
    Type="String",
    AllowedValues=["True", "False"],
    Default="True",
)
LOG_GROUP_NAME_T = "ServicesLogGroupName"
LOG_GROUP_NAME = Parameter(LOG_GROUP_NAME_T, Type="String", Default="ComposeXDefined")
LOG_GROUP_RETENTION_T = "ServiceLogGroupRetentionPeriod"
LOG_GROUP_RETENTION = Parameter(
    LOG_GROUP_RETENTION_T,
    Type="Number",
    Default=30,
    AllowedValues=[
        1,
        3,
        5,
        7,
        14,
        30,
        60,
        90,
        120,
        150,
        180,
        365,
        400,
        545,
        731,
        1827,
        3653,
    ],
)

FARGATE_MODES = {
    256: [2 ** i for i in [9, 10, 11]],
    512: [(2 ** 10) * i for i in range(1, 5)],
    1024: [(2 ** 10) * i for i in range(2, 9)],
    2048: [(2 ** 10) * i for i in range(4, 17)],
    4096: [(2 ** 10) * i for i in range(8, 33)],
}

FARGATE_MODES_VALUES = []
for cpu in FARGATE_MODES.keys():
    for ram in FARGATE_MODES[cpu]:
        FARGATE_MODES_VALUES.append(f"{cpu}!{ram}")

FARGATE_CPU_RAM_CONFIG_T = "FargateCpuRamConfiguration"
FARGATE_CPU_RAM_CONFIG = Parameter(
    FARGATE_CPU_RAM_CONFIG_T,
    Type="String",
    AllowedValues=FARGATE_MODES_VALUES,
    Default="256!512",
)

FARGATE_CPU = Select(0, Split("!", Ref(FARGATE_CPU_RAM_CONFIG)))
FARGATE_RAM = Select(1, Split("!", Ref(FARGATE_CPU_RAM_CONFIG)))

CLUSTER_SG_ID_T = "ClusterWideSGId"
CLUSTER_SG_ID = Parameter(
    CLUSTER_SG_ID_T,
    Type="String",
    Default="none",
    AllowedPattern=r"(none|^sg-[a-z0-9]+$)",
)

SERVICE_GROUP_ID_T = "ServiceGroupId"
SERVICE_GROUP_ID = Parameter(SERVICE_GROUP_ID_T, Type=SG_ID_TYPE, Default="<none>")

AWS_XRAY_IMAGE = "public.ecr.aws/xray/aws-xray-daemon:latest"
XRAY_IMAGE_T = "AWSXRayImage"
XRAY_IMAGE = Parameter(XRAY_IMAGE_T, Type="String", Default=AWS_XRAY_IMAGE)


def get_import_service_group_id(remote_service_name):
    """
    Function to return the ImportValue(Sub()) for given ecs_service name
    """
    return ImportValue(
        Sub(
            f"${{{ROOT_STACK_NAME_T}}}{delim}{remote_service_name}{delim}{SERVICE_GROUP_ID_T}"
        )
    )
