# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only

"""
Conditions relative to the Compute stack.
"""

from troposphere import Equals, Ref
from ecs_composex.compute import compute_params

MAX_IS_MIN_T = "CapacityMaxIsMinCondition"
MAX_IS_MIN = Equals(Ref(compute_params.MAX_CAPACITY), 0)
