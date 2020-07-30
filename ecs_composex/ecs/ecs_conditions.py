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
Parameters relating to ECS.

This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from troposphere import Condition, Ref, Equals, And, Not

from ecs_composex.ecs import ecs_params

GENERATED_CLUSTER_NAME_CON_T = "UsCfnGeneratedClusterName"
GENERATED_CLUSTER_NAME_CON = Equals(
    Ref(ecs_params.CLUSTER_NAME), ecs_params.CLUSTER_NAME.Default
)

NOT_USE_CLUSTER_SG_CON_T = "NotUseClusterSecurityGroupCondition"
NOT_USE_CLUSTER_SG_CON = Equals(
    Ref(ecs_params.CLUSTER_SG_ID), ecs_params.CLUSTER_SG_ID.Default
)

USE_CLUSTER_SG_CON_T = "UseClusterSecurityGroupCondition"
USE_CLUSTER_SG_CON = Not(Condition(NOT_USE_CLUSTER_SG_CON_T))

SERVICE_COUNT_ZERO_CON_T = "ServiceCountIsZeroCondition"
SERVICE_COUNT_ZERO_CON = Equals(Ref(ecs_params.SERVICE_COUNT), "0")

USE_FARGATE_CON_T = "UseFargateCondition"
USE_FARGATE_CON = Equals(Ref(ecs_params.LAUNCH_TYPE), "FARGATE")

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

USE_CLUSTER_CAPACITY_PROVIDERS_CON_T = "UseClusterDefaultCapacityProviders"
USE_CLUSTER_CAPACITY_PROVIDERS_CON = Equals(
    Ref(ecs_params.LAUNCH_TYPE), ecs_params.LAUNCH_TYPE.Default
)
