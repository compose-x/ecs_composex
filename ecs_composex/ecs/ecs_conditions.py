# -*- coding: utf-8 -*-
"""
Parameters relating to ECS.

This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from troposphere import (
    Condition,
    Ref, Equals, And
)

from ecs_composex.ecs import ecs_params

SERVICE_COUNT_ZERO_CON_T = 'ServiceCountIsZeroCondition'
SERVICE_COUNT_ZERO_CON = Equals(
    Ref(ecs_params.SERVICE_COUNT),
    '0'
)

MEM_RES_IS_MEM_ALLOC_CON_T = 'MemoryReservedIsMemoryAllocatedCondition'
MEM_RES_IS_MEM_ALLOC_CON = Equals(
    Ref(ecs_params.MEMORY_RES),
    ecs_params.MEMORY_RES.Default
)

USE_FARGATE_CON_T = 'UseFargateCondition'
USE_FARGATE_CON = Equals(
    Ref(ecs_params.LAUNCH_TYPE),
    'FARGATE'
)

SERVICE_COUNT_ZERO_AND_FARGATE_CON_T = 'ServiceCountZeroAndFargate'
SERVICE_COUNT_ZERO_AND_FARGATE_CON = And(
    Condition(USE_FARGATE_CON_T),
    Condition(SERVICE_COUNT_ZERO_CON_T)
)
