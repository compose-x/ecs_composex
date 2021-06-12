#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Conditions relative to the Compute stack.
"""

from troposphere import Equals, Ref

from ecs_composex.compute import compute_params

MAX_IS_MIN_T = "CapacityMaxIsMinCondition"
MAX_IS_MIN = Equals(Ref(compute_params.MAX_CAPACITY), 0)
