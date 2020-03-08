# -*- coding: utf-8 -*-
"""Conditions related to the VPC construction."""

from troposphere import (
    Condition, Equals,
    Ref, Or, Not
)

from ecs_composex.vpc import vpc_params
from ecs_composex.common import cfn_conditions

USE_SUB_ZONE_CON_T = 'UseDnsSubZoneCondition'
USE_SUB_ZONE_CON = Or(
    Equals(
        Ref(vpc_params.USE_SUB_ZONE),
        'True'
    ),
    Condition(cfn_conditions.NOT_USE_CLOUDMAP_CON_T)
)

NOT_USE_VPC_MAP_ID_CON_T = 'NotUseVpcMapId'
NOT_USE_VPC_MAP_ID_CON = Equals(
    Ref(vpc_params.VPC_MAP_ID),
    vpc_params.VPC_MAP_ID.Default
)

USE_VPC_MAP_ID_CON_T = 'UseVpcMapId'
USE_VPC_MAP_ID_CON = Not(Condition(NOT_USE_VPC_MAP_ID_CON_T))
