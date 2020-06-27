#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

Module for ACM Conditions

"""

from troposphere import Equals, Not, Ref, And, Condition
from ecs_composex.acm.acm_params import (
    VALIDATION_DOMAIN_NAME,
    VALIDATION_DOMAIN_ZONE_ID,
)

ACM_ZONE_ID_IS_NONE_T = "AcmZoneIsNoneCondition"
ACM_ZONE_ID_IS_NONE = Equals(
    Ref(VALIDATION_DOMAIN_ZONE_ID), VALIDATION_DOMAIN_ZONE_ID.Default
)

ACM_ZONE_NAME_IS_NONE_T = "AcmZoneNameIsNoneCondition"
ACM_ZONE_NAME_IS_NONE = Equals(
    Ref(VALIDATION_DOMAIN_NAME), VALIDATION_DOMAIN_NAME.Default
)

USE_ZONE_ID_T = "UseZoneIdOverZoneNameForValidation"
USE_ZONE_ID = And(
    Not(Condition(ACM_ZONE_ID_IS_NONE_T)), Not(Condition(ACM_ZONE_NAME_IS_NONE_T))
)


def add_all_conditions(template):
    """
    Function to add all conditions to the template
    :param template:
    :return:
    """
    template.add_condition(ACM_ZONE_ID_IS_NONE_T, ACM_ZONE_ID_IS_NONE)
    template.add_condition(ACM_ZONE_NAME_IS_NONE_T, ACM_ZONE_NAME_IS_NONE)
    template.add_condition(USE_ZONE_ID_T, USE_ZONE_ID)
