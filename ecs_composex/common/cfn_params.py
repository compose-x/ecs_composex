# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


""""
Common parameters for CFN
This is a crucial part as all the titles, marked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from troposphere import Parameter

COMPUTE_STACK_NAME = "Ec2Compute"
VPC_STACK_NAME = "vpc"
MESH_TITLE = "RootMesh"
PRIVATE_MAP_TITLE = "CloudMapVpcNamespace"
PUBLIC_MAP_TITLE = "CloudMapPublicNamespace"

ROOT_STACK_NAME_T = "RootStackName"
ROOT_STACK_NAME = Parameter(
    ROOT_STACK_NAME_T,
    Type="String",
    Default="self",
    Description="When part of a combined deployment, represents to the top stack name",
)

VPC_MAP_ID_T = "AwsVpcCloudMapId"
VPC_MAP_ID = Parameter(VPC_MAP_ID_T, Type="String", Default="none")


VPC_MAP_ARN_T = "AwsVpcCloudMapArn"
VPC_MAP_ARN = Parameter(VPC_MAP_ARN_T, Type="String", Default="none")

USE_CLOUDMAP_T = "UseAwsCloudMap"
USE_CLOUDMAP = Parameter(
    USE_CLOUDMAP_T, Type="String", AllowedValues=["True", "False"], Default="True"
)

USE_APP_MESH_T = "UseAwsAppMesh"
USE_APP_MESH = Parameter(
    USE_APP_MESH_T, Type="String", AllowedValues=["True", "False"], Default="True"
)

USE_CFN_PARAMS_T = "UseCfnParametersValue"
USE_CFN_PARAMS = Parameter(
    USE_CFN_PARAMS_T, Type="String", AllowedValues=["True", "False"], Default=True
)

USE_CFN_EXPORTS_T = "UseCfnExports"
USE_CFN_EXPORTS = Parameter(
    USE_CFN_EXPORTS_T, Type="String", AllowedValues=["True", "False"], Default="True"
)

USE_SSM_EXPORTS_T = "UseSsmExports"
USE_SSM_EXPORTS = Parameter(
    USE_SSM_EXPORTS_T, Type="String", AllowedValues=["True", "False"], Default="False"
)

USE_FLEET_T = "UseSpotFleetHosts"
USE_FLEET = Parameter(
    USE_FLEET_T, Type="String", Default="False", AllowedValues=["True", "False"]
)

USE_ONDEMAND_T = "UseOnDemandHosts"
USE_ONDEMAND = Parameter(
    USE_ONDEMAND_T, Type="String", Default="False", AllowedValues=["True", "False"]
)
