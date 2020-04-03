# -*- coding: utf-8 -*-

from troposphere import Condition, Equals, Ref, Not
from ecs_composex.compute import compute_params

MAX_IS_MIN_T = "CapacityMaxIsMinCondition"
MAX_IS_MIN = Equals(Ref(compute_params.MAX_CAPACITY), 0)
