# -*- coding: utf-8 -*-

from troposphere import (
    Condition, Equals, Ref, Not
)
from ecs_composex.compute import compute_params
USE_SPOT_CON_T = 'UseSpotFleetHostsCondition'
USE_SPOT_CON = Equals(
    Ref(compute_params.USE_FLEET),
    'True'
)

NOT_USE_SPOT_CON_T = 'NotUseSpotFleetHostsCondition'
NOT_USE_SPOT_CON = Not(
    Condition(USE_SPOT_CON_T)
)

MAX_IS_MIN_T = 'CapacityMaxIsMinCondition'
MAX_IS_MIN = Equals(
    Ref(compute_params.MAX_CAPACITY),
    0
)
