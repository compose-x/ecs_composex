#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Parameters relating to ECS.

This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from troposphere import And, Condition, Equals, Not, Or, Ref

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


USE_LAUNCH_TYPE_CON_T = "UseLaunchType"
USE_LAUNCH_TYPE_CON = Or(Condition(USE_EC2_CON_T), Condition(USE_FARGATE_LT_CON_T))


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

CREATE_CLUSTER_CON_T = "CreateClusterCondition"
CREATE_CLUSTER_CON = Equals(Ref(ecs_params.CREATE_CLUSTER), "True")
GENERATED_CLUSTER_NAME_CON_T = "GenerateEcsClusterName"
GENERATED_CLUSTER_NAME_CON = Not(
    Equals(Ref(ecs_params.CLUSTER_NAME), ecs_params.CLUSTER_NAME.Default)
)

CREATE_LOG_GROUP_CON_T = "CreateNewLogGroupCondition"
CREATE_LOG_GROUP_CON = Equals(Ref(ecs_params.CREATE_LOG_GROUP), "True")
GENERATED_LOG_GROUP_NAME_CON_T = "GenerateLogGroupName"
GENERATED_LOG_GROUP_NAME_CON = Equals(
    Ref(ecs_params.LOG_GROUP_NAME), ecs_params.LOG_GROUP_NAME.Default
)
