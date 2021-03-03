# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@compose-x.io>
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

from troposphere import Parameter as CfnParameter

COMPUTE_STACK_NAME = "Ec2Compute"
VPC_STACK_NAME = "vpc"
MESH_TITLE = "RootMesh"
PRIVATE_MAP_TITLE = "CloudMapVpcNamespace"
PUBLIC_MAP_TITLE = "CloudMapPublicNamespace"
PUBLIC_ZONE_TITLE = "Route53PublicZone"


class Parameter(CfnParameter):
    """
    Class to extend the default Parameter behaviour
    """

    def __init__(self, title, return_value=None, **kwargs):
        self.return_value = return_value
        super().__init__(title, **kwargs)


ROOT_STACK_NAME_T = "RootStackName"
ROOT_STACK_NAME = Parameter(
    ROOT_STACK_NAME_T,
    Type="String",
    Default="self",
    Description="When part of a combined deployment, represents to the top stack name",
)

USE_FLEET_T = "UseSpotFleetHosts"
USE_FLEET = Parameter(
    USE_FLEET_T, Type="String", Default="False", AllowedValues=["True", "False"]
)

USE_ONDEMAND_T = "UseOnDemandHosts"
USE_ONDEMAND = Parameter(
    USE_ONDEMAND_T, Type="String", Default="False", AllowedValues=["True", "False"]
)
