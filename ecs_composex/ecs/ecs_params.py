# -*- coding: utf-8 -*-
"""
Parameters bound to  ecs_composex.ecs
This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it [a-zA-Z0-9]
"""

from troposphere import Parameter, Select, Split, Ref, ImportValue, Sub

from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

LOG_GROUP_T = 'ServicesLogGroup'
SG_T = 'ServiceSecurityGroup'
NETWORK_MODE = 'awsvpc'
EXEC_ROLE_T = 'EcsExecutionRole'
TASK_ROLE_T = 'EcsTaskRole'
SERVICE_T = 'EcsServiceDefinition'
TASK_T = 'EcsTaskDefinition'
RES_KEY = 'services'

LAUNCH_TYPE_T = 'EcsLaunchType'
LAUNCH_TYPE = Parameter(
    LAUNCH_TYPE_T, Type='String',
    AllowedValues=['EC2', 'FARGATE'],
    Default='FARGATE'
)

IS_PUBLIC_T = 'ExposeServicePublicly'
IS_PUBLIC = Parameter(
    IS_PUBLIC_T,
    AllowedValues=['True', 'False'],
    Type='String'
)

TASK_CPU_COUNT_T = 'TaskCpuCount'
TASK_CPU_COUNT = Parameter(
    TASK_CPU_COUNT_T,
    Type='Number',
    Default=1024
)
MEMORY_ALLOC_T = 'ContainerMemoryAllocation'
MEMORY_RES_T = 'ContainerMemoryReservation'

MEMORY_ALLOC = Parameter(MEMORY_ALLOC_T, Type='Number', Default=512)
MEMORY_RES = Parameter(MEMORY_RES_T, Type='Number', Default=0)

CLUSTER_NAME_T = 'EcsClusterName'
CLUSTER_NAME = Parameter(
    CLUSTER_NAME_T, Type='String',
    AllowedPattern=r'[a-zA-Z0-9-]+',
    Default='default'
)

SERVICE_NAME_T = 'MicroServiceName'
SERVICE_NAME = Parameter(
    SERVICE_NAME_T, Type='String',
    AllowedPattern=r'[a-zA-Z0-9-]+'
)

SERVICE_IMAGE_T = 'MicroserviceImage'
SERVICE_IMAGE = Parameter(SERVICE_IMAGE_T, Type='String')

SERVICE_COUNT_T = 'MicroservicesCount'
SERVICE_COUNT = Parameter(
    SERVICE_COUNT_T,
    Type='Number',
    MinValue=0,
    Default=0
)

ELB_GRACE_PERIOD_T = 'ElbGracePeriod'
ELB_GRACE_PERIOD = Parameter(
    ELB_GRACE_PERIOD_T,
    Type='Number',
    MinValue=0,
    Default=90,
    MaxValue=300
)

ECS_CONTROLLER_T = 'EcsServiceDeploymentController'
ECS_CONTROLLER = Parameter(
    ECS_CONTROLLER_T,
    Type='String',
    AllowedValues=[
        'ECS',
        'CODE_DEPLOY',
        'EXTERNAL'
    ],
    Default='ECS'
)

LOG_GROUP = Parameter(
    f"Cluster{LOG_GROUP_T}",
    Type='String'
)

FARGATE_CPU_RAM_CONFIG_T = 'FargateCpuRamConfiguration'
FARGATE_CPU_RAM_CONFIG = Parameter(
    FARGATE_CPU_RAM_CONFIG_T,
    Type='String',
    AllowedValues=[
        '256!512',
        '256!1024',
        '256!2048',
        '512!1024',
        '512!2048',
        '512!3072',
        '512!4096',
        '1024!2048',
        '1024!3072',
        '1024!4096',
        '1024!5120',
        '1024!6144',
        '1024!7168',
        '1024!8192',
        '2048!2048',
        '2048!3072',
        '2048!4096',
        '2048!5120',
        '2048!6144',
        '2048!7168',
        '2048!8192',
        '2048!9216',
        '2048!10240',
        '2048!11264',
        '2048!12288',
        '2048!13312',
        '2048!14336',
        '2048!15360',
        '2048!16384',
        '4096!8192',
        '4096!9216',
        '4096!10240',
        '4096!11264',
        '4096!12288',
        '4096!13312',
        '4096!14336',
        '4096!15360',
        '4096!16384',
        '4096!17408',
        '4096!18432',
        '4096!19456',
        '4096!20480',
        '4096!21504',
        '4096!22528',
        '4096!23552',
        '4096!24576',
        '4096!25600',
        '4096!26624',
        '4096!27648',
        '4096!28672',
        '4096!29696',
        '4096!30720'
    ],
    Default='512!1024'
)

FARGATE_CPU = Select(0, Split('!', Ref(FARGATE_CPU_RAM_CONFIG)))
FARGATE_RAM = Select(1, Split('!', Ref(FARGATE_CPU_RAM_CONFIG)))

CLUSTER_SG_ID_T = 'ClusterWideSGId'
CLUSTER_SG_ID = Parameter(
    CLUSTER_SG_ID_T,
    Type=SG_ID_TYPE,
    Default='<none>'
)

SERVICE_GROUP_ID_T = 'ServiceGroupId'
SERVICE_GROUP_ID = Parameter(
    SERVICE_GROUP_ID_T,
    Type=SG_ID_TYPE,
    Default='<none>'
)


def get_import_service_group_id(remote_service_name):
    """
    Function to return the ImportValue(Sub()) for given service name
    """
    return ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{remote_service_name}-{SERVICE_GROUP_ID_T}"))
