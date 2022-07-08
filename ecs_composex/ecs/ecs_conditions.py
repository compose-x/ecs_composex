# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Parameters relating to ECS.

This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from troposphere import And, Condition, Equals, If, Not, Or, Ref

from ecs_composex.ecs import ecs_params

NOT_USE_CLUSTER_SG_CON_T = "NotUseClusterSecurityGroupCondition"
NOT_USE_CLUSTER_SG_CON = Equals(
    Ref(ecs_params.CLUSTER_SG_ID), ecs_params.CLUSTER_SG_ID.Default
)

USE_CLUSTER_SG_CON_T = "UseClusterSecurityGroupCondition"
USE_CLUSTER_SG_CON = Not(Condition(NOT_USE_CLUSTER_SG_CON_T))

SERVICE_COUNT_ZERO_CON_T = "ServiceCountIsZeroCondition"
SERVICE_COUNT_ZERO_CON = Equals(Ref(ecs_params.SERVICE_COUNT), "0")

USE_EC2_CON_T = "UseEC2LaunchType"
USE_EC2_CON = Equals(Ref(ecs_params.LAUNCH_TYPE), "EC2")


USE_FARGATE_PROVIDERS_CON_T = "UseFargateProvidersCondition"
USE_FARGATE_PROVIDERS_CON = Equals(Ref(ecs_params.LAUNCH_TYPE), "FARGATE_PROVIDERS")

USE_FARGATE_LT_CON_T = "UseFargateLaunchType"
USE_FARGATE_LT_CON = Equals(Ref(ecs_params.LAUNCH_TYPE), "FARGATE")

USE_CLUSTER_MODE_CON_T = "UseClusterDefaultProviders"
USE_CLUSTER_MODE_CON = Equals(Ref(ecs_params.LAUNCH_TYPE), "CLUSTER_MODE")

USE_SERVICE_MODE_CON_T = "UseServiceProviders"
USE_SERVICE_MODE_CON = Equals(Ref(ecs_params.LAUNCH_TYPE), "SERVICE_MODE")

USE_FARGATE_CON_T = "UseFargate"
USE_FARGATE_CON = Or(
    Condition(USE_FARGATE_PROVIDERS_CON_T), Condition(USE_FARGATE_LT_CON_T)
)

NOT_FARGATE_CON_T = "NotUsingFargate"
NOT_FARGATE_CON = Not(Condition(USE_FARGATE_CON_T))

USE_EXTERNAL_LT_T = "UseExternalLaunchType"
USE_EXTERNAL_LT = Equals(Ref(ecs_params.LAUNCH_TYPE), "EXTERNAL")


USE_LAUNCH_TYPE_CON_T = "UseLaunchType"
USE_LAUNCH_TYPE_CON = Or(
    Condition(USE_EC2_CON_T),
    Condition(USE_FARGATE_LT_CON_T),
    Condition(USE_EXTERNAL_LT_T),
)

USE_LINUX_OS_T = "UseLinuxOS"
USE_LINUX_OS = Equals(
    Ref(ecs_params.RUNTIME_OS_FAMILY), ecs_params.RUNTIME_OS_FAMILY.Default
)

USE_WINDOWS_OS_T = "UseWindowsOS"
USE_WINDOWS_OS = Not(Condition(USE_LINUX_OS_T))

USE_WINDOWS_OR_FARGATE_T = "UseWindowsOSorFargate"
USE_WINDOWS_OR_FARGATE = Or(Condition(USE_WINDOWS_OS_T), Condition(USE_FARGATE_CON_T))

IPC_FROM_HOST_CON_T = "IpcSetForHost"
IPC_FROM_HOST_CON = Equals(Ref(ecs_params.IPC_MODE), "host")

USE_EC2_OR_EXTERNAL_LT_CON_T = "UseEC2orExternal"
USE_EC2_OR_EXTERNAL_LT_CON = Or(Condition(USE_EXTERNAL_LT_T), Condition(USE_EC2_CON_T))

SERVICE_COUNT_ZERO_AND_FARGATE_CON_T = "ServiceCountZeroAndFargate"
SERVICE_COUNT_ZERO_AND_FARGATE_CON = And(
    Condition(USE_FARGATE_CON_T), Condition(SERVICE_COUNT_ZERO_CON_T)
)

NOT_USE_HOSTNAME_CON_T = "NotUseMicroserviceHostnameCondition"
NOT_USE_HOSTNAME_CON = Equals(
    Ref(ecs_params.SERVICE_HOSTNAME), ecs_params.SERVICE_HOSTNAME.Default
)

USE_HOSTNAME_CON_T = "UseMicroserviceHostnameCondition"
USE_HOSTNAME_CON = Not(Condition(NOT_USE_HOSTNAME_CON_T))

DISABLE_CAPACITY_PROVIDERS_CON_T = "DisableCapacityProviders"
DISABLE_CAPACITY_PROVIDERS_CON = Or(
    Condition(USE_LAUNCH_TYPE_CON_T), Condition(USE_CLUSTER_MODE_CON_T)
)

USE_BRIDGE_NETWORKING_MODE_CON_T = "UseBridgeNetworkingMode"
USE_BRIDGE_NETWORKING_MODE_CON = Equals(Ref(ecs_params.NETWORK_MODE), "bridge")

USE_AWSVPC_NETWORKING_MODE_CON_T = "UseAwsvpcNetworkingMode"
USE_AWSVPC_NETWORKING_MODE_CON = Equals(Ref(ecs_params.NETWORK_MODE), "awsvpc")


def use_external_lt_con(if_true, if_false) -> If:
    """
    Function to return the If() to simplify !If USE_EXTERNAL_LT_T

    :return: If(USE_EXTERNAL_LT_T, if_true, if_false)
    :rtype: If
    """
    return If(USE_EXTERNAL_LT_T, if_true, if_false)
