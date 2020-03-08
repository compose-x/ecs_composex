# -*- coding: utf-8 -*-

from troposphere import (
    Condition, Equals, Ref, Not, And
)


from ecs_composex.cluster import cluster_params
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T

GENERATED_CLUSTER_NAME_CON_T = 'UsCfnGeneratedClusterName'
GENERATED_CLUSTER_NAME_CON = Equals(
    Ref(cluster_params.CLUSTER_NAME),
    cluster_params.CLUSTER_NAME.Default
)

CLUSTER_NAME_CON_T = 'SetClusterNameFromRootStack'
CLUSTER_NAME_CON = And(
    Condition(USE_STACK_NAME_CON_T),
    Condition(GENERATED_CLUSTER_NAME_CON_T)
)

USE_SPOT_CON_T = 'UseSpotFleetHostsCondition'
USE_SPOT_CON = Equals(
    Ref(cluster_params.USE_FLEET),
    'True'
)

NOT_USE_SPOT_CON_T = 'NotUseSpotFleetHostsCondition'
NOT_USE_SPOT_CON = Not(
    Condition(USE_SPOT_CON_T)
)

MAX_IS_MIN_T = 'CapacityMaxIsMinCondition'
MAX_IS_MIN = Equals(
    Ref(cluster_params.MAX_CAPACITY),
    0
)
