#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

""""
Common parameters for CFN
This is a crucial part as all the titles, marked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it Alphanumerical [a-zA-Z0-9]
"""

from troposphere import AWS_STACK_ID
from troposphere import Parameter as CfnParameter
from troposphere import Ref, Select, Split, Sub

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
    USE_ONDEMAND_T,
    Type="String",
    Default="False",
    AllowedValues=["True", "False"],
)

STACK_ID_SHORT = Select(0, Split("-", Select(1, Split("/", Ref(AWS_STACK_ID)))))
