# -*- coding: utf-8 -*-

"""Common Conditions across the templates"""

from ecs_composex.common import cfn_params
from troposphere import (
    Condition, Not,
    Ref, Equals, And
)

USE_STACK_NAME_CON_T = 'UseStackName'
USE_STACK_NAME_CON = Equals(
    Ref(cfn_params.ROOT_STACK_NAME),
    cfn_params.ROOT_STACK_NAME.Default
)

USE_CLOUDMAP_CON_T = 'UseCloudMapCondition'
USE_CLOUDMAP_CON = Equals(
    Ref(cfn_params.SERVICE_DISCOVERY_T),
    'True'
)

NOT_USE_CLOUDMAP_CON_T = 'NotUseCloudMapCondition'
NOT_USE_CLOUDMAP_CON = Not(Condition(USE_CLOUDMAP_CON_T))

USE_CFN_PARAMS_CON_T = 'UseCfnParametersValueCondition'
USE_CFN_PARAMS_CON = Equals(
    Ref(cfn_params.USE_CFN_PARAMS),
    cfn_params.USE_CFN_PARAMS.Default
)

NOT_USE_CFN_PARAMS_CON_T = f"Not{USE_CFN_PARAMS_CON_T}"
NOT_USE_CFN_PARAMS_CON = Not(Condition(USE_CFN_PARAMS_CON_T))

USE_CFN_EXPORTS_T = 'UseExportsCondition'
USE_CFN_EXPORTS = Equals(
    Ref(cfn_params.USE_CFN_EXPORTS),
    'True'
)

NOT_USE_CFN_EXPORTS_T = 'NotUseCfnExportsCondition'
NOT_USE_CFN_EXPORTS = Not(Condition(USE_CFN_EXPORTS_T))

USE_SSM_EXPORTS_T = 'UseSsmExportsCondition'
USE_SSM_EXPORTS = Equals(
    Ref(cfn_params.USE_SSM_EXPORTS),
    'True'
)

USE_CFN_AND_SSM_EXPORTS_T = 'UseCfnAndSsmCondition'
USE_CFN_AND_SSM_EXPORTS = And(
    Condition(USE_CFN_EXPORTS_T),
    Condition(USE_SSM_EXPORTS_T)
)

USE_SSM_ONLY_T = 'UseSsmOnlyCondition'
USE_SSM_ONLY = And(
    Condition(USE_SSM_EXPORTS_T),
    Condition(NOT_USE_CFN_EXPORTS_T)
)
