# -*- coding: utf-8 -*-
""""
Common parameters for CFN
This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from troposphere import Parameter


ROOT_STACK_NAME_T = 'RootStackName'
ROOT_STACK_NAME = Parameter(
    ROOT_STACK_NAME_T, Type='String', Default='<self>',
    Description='When part of a combined deployment, represents to the top stack name'
)

VPC_MAP_ID_T = 'AwsVpcCloudMapId'
VPC_MAP_ID = Parameter(VPC_MAP_ID_T, Type='String', Default='none')


VPC_MAP_ARN_T = 'AwsVpcCloudMapArn'
VPC_MAP_ARN = Parameter(VPC_MAP_ARN_T, Type='String', Default='none')

SERVICE_DISCOVERY_T = 'UseAwsCloudMap'
SERVICE_DISCOVERY = Parameter(
    SERVICE_DISCOVERY_T,
    Type='String',
    AllowedValues=['True', 'False'],
    Default='True'
)

USE_CFN_PARAMS_T = 'UseCfnParametersValue'
USE_CFN_PARAMS = Parameter(
    USE_CFN_PARAMS_T,
    Type='String',
    AllowedValues=['True', 'False'], Default=True
)

USE_CFN_EXPORTS_T = 'UseCfnExports'
USE_CFN_EXPORTS = Parameter(
    USE_CFN_EXPORTS_T, Type='String',
    AllowedValues=['True', 'False'], Default='True'
)

USE_SSM_EXPORTS_T = 'UseSsmExports'
USE_SSM_EXPORTS = Parameter(
    USE_SSM_EXPORTS_T, Type='String',
    AllowedValues=['True', 'False'], Default='False'
)
