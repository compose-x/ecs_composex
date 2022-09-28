# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Parameters bound to  ecs_composex.ecs
This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it [a-zA-Z0-9]
"""

from troposphere import ImportValue, Ref, Select, Split, Sub

from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, Parameter
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.vpc.vpc_params import SG_ID_TYPE, SUBNETS_TYPE

CLUSTER_T = "EcsCluster"
LOG_GROUP_T = "ServicesLogGroup"
SG_T = "ServiceSecurityGroup"
EXEC_ROLE_T = "EcsExecutionRole"
TASK_ROLE_T = "EcsTaskRole"
SERVICE_T = "EcsServiceDefinition"
TASK_T = "EcsTaskDefinition"
RES_KEY = "services"
ECS_TASK_FAMILY_LABEL = "ecs.task.family"
SERVICE_SCALING_TARGET = "ServiceScalingTarget"

ECS_COMPUTE_SETTINGS = "ECS Compute Settings"
LOGGING_SETTINGS = "Logging Settings"
FARGATE_SETTINGS = "AWS Fargate Settings"

LAUNCH_TYPE_T = "EcsLaunchType"
LAUNCH_TYPE = Parameter(
    LAUNCH_TYPE_T,
    group_label=ECS_COMPUTE_SETTINGS,
    label="Defines the Launch Type to use for ECS Service",
    Type="String",
    AllowedValues=[
        "EC2",
        "FARGATE",
        "EXTERNAL",
        "FARGATE_PROVIDERS",
        "CLUSTER_MODE",
        "SERVICE_MODE",
    ],
    Default="FARGATE",
)

FARGATE_VERSION_T = "FargatePlatformVersion"
FARGATE_VERSION = Parameter(
    FARGATE_VERSION_T,
    group_label=ECS_COMPUTE_SETTINGS,
    label="Fargate platform version",
    Type="String",
    AllowedValues=["DEFAULT", "1.4.0", "1.3.0"],
    Default="1.4.0",
)


CLUSTER_NAME_T = "EcsCluster"
CLUSTER_NAME = Parameter(
    CLUSTER_NAME_T,
    Type="String",
    AllowedPattern=r"[a-zA-Z0-9-]+",
    Default="default",
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

SERVICE_COUNT_T = "MicroservicesCount"
SERVICE_COUNT = Parameter(
    SERVICE_COUNT_T,
    group_label=ECS_COMPUTE_SETTINGS,
    Description="Defines how many containers by default the service should have",
    Type="Number",
    MinValue=0,
    Default=0,
)

ELB_GRACE_PERIOD_T = "ElbGracePeriod"
ELB_GRACE_PERIOD = Parameter(
    ELB_GRACE_PERIOD_T,
    Type="Number",
    MinValue=0,
    Default=300,
    MaxValue=2147483647,
)

LOG_GROUP_RETENTION_T = "ServiceLogGroupRetentionPeriod"
LOG_GROUP_RETENTION = Parameter(
    LOG_GROUP_RETENTION_T,
    group_label=LOGGING_SETTINGS,
    label="Name of the CW Log Group to store the containers logs into",
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

RUNTIME_CPU_ARCHITECTURE_T = "RuntimeCpuArchitecture"
RUNTIME_CPU_ARCHITECTURE = Parameter(
    RUNTIME_CPU_ARCHITECTURE_T,
    group_label=ECS_COMPUTE_SETTINGS,
    label="Choose CPU Architecture to use for your services",
    Type="String",
    AllowedValues=["X86_64", "ARM64"],
    Default="X86_64",
)


RUNTIME_OS_FAMILY_T = "RuntimeOperatingSystemFamily"
RUNTIME_OS_FAMILY = Parameter(RUNTIME_OS_FAMILY_T, Type="String", Default="LINUX")


FARGATE_MODES = {
    256: [2**i for i in [9, 10, 11]],
    512: [(2**10) * i for i in range(1, 5)],
    1024: [(2**10) * i for i in range(2, 9)],
    2048: [(2**10) * i for i in range(4, 17)],
    4096: [(2**10) * i for i in range(8, 33)],
    8192: [(2**10) * i for i in range(16, 61, 4)],
    16384: [(2**10) * i for i in range(32, 121, 8)],
}

FARGATE_MODES_VALUES = []
for cpu in FARGATE_MODES.keys():
    for ram in FARGATE_MODES[cpu]:
        FARGATE_MODES_VALUES.append(f"{cpu}!{ram}")

FARGATE_CPU_RAM_CONFIG_T = "FargateCpuRamConfiguration"
FARGATE_CPU_RAM_CONFIG = Parameter(
    FARGATE_CPU_RAM_CONFIG_T,
    group_label=FARGATE_SETTINGS,
    Description="AWS Fargate CPU/RAM combination for your ECS Task",
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


NETWORK_MODE_T = "TaskNetworkingMode"
NETWORK_MODE = Parameter(
    NETWORK_MODE_T,
    Type="String",
    AllowedValues=["awsvpc", "bridge", "host", "none"],
    Default="awsvpc",
)

IPC_MODE_T = "TaskIpcMode"
IPC_MODE = Parameter(
    IPC_MODE_T, Type="String", AllowedValues=["task", "host", "none"], Default="none"
)

SERVICE_SUBNETS_T = "ECSServiceSubnets"
SERVICE_SUBNETS = Parameter(SERVICE_SUBNETS_T, Type=SUBNETS_TYPE)


def get_import_service_group_id(remote_service_name):
    """
    Function to return the ImportValue(Sub()) for given ecs_service name
    """
    return ImportValue(
        Sub(
            f"${{{ROOT_STACK_NAME_T}}}{DELIM}{remote_service_name}{DELIM}{SERVICE_GROUP_ID_T}"
        )
    )
