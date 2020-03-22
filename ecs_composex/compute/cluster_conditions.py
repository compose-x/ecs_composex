# -*- coding: utf-8 -*-

from troposphere import (
    Condition, Equals, Ref, Not
)
from ecs_composex.compute import cluster_params
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
