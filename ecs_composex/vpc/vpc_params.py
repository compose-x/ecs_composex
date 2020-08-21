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

"""
Parameters related to the VPC settings. Used by ecs_composex.vpc and others
"""

from troposphere import Parameter

VPC_TYPE = "AWS::EC2::VPC::Id"
AMI_TYPE = "AWS::EC2::Image::Id"
SUBNET_TYPE = "AWS::EC2::Subnet::Id"
SUBNETS_TYPE = "List<AWS::EC2::Subnet::Id>"
R53_TYPE = "AWS::Route53::HostedZone::Id"
AZS_TYPE = "List<AWS::EC2::AvailabilityZone::Name>"
SG_ID_TYPE = "AWS::EC2::SecurityGroup::Id"
SG_NAME_TYPE = "AWS::EC2::SecurityGroup::GroupName"

DEFAULT_VPC_CIDR = "100.64.72.0/24"
DEFAULT_SINGLE_NAT = True


VPC_T = "Vpc"
IGW_T = "InternetGatewayV4"

RES_KEY = "vpc"
VPC_ID_T = "VpcId"
VPC_ID = Parameter(VPC_ID_T, Type=VPC_TYPE)

VPC_CIDR_T = "VpcCidr"
VPC_CIDR = Parameter(VPC_CIDR_T, Type="String", Default=DEFAULT_VPC_CIDR)

VPC_SINGLE_NAT_T = "SingleNat"
VPC_SINGLE_NAT = Parameter(VPC_SINGLE_NAT_T, Type="String", Default="True")

STORAGE_SUBNETS_CIDR_T = "StorageSubnetsCidr"
STORAGE_SUBNETS_CIDR = Parameter(STORAGE_SUBNETS_CIDR_T, Type="CommaDelimitedList")
STORAGE_SUBNETS_T = "StorageSubnets"
STORAGE_SUBNETS = Parameter(STORAGE_SUBNETS_T, Type=SUBNETS_TYPE)

BACKEND_SUBNETS_CIDR_T = "BackendSubnetsCidr"
BACKEND_SUBNETS_CIDR = Parameter(BACKEND_SUBNETS_CIDR_T, Type="CommaDelimitedList")
BACKEND_SUBNETS_T = "BackendSubnets"
BACKEND_SUBNETS = Parameter(BACKEND_SUBNETS_T, Type=SUBNETS_TYPE)

PUBLIC_SUBNETS_CIDR_T = "PublicSubnetsCidr"
PUBLIC_SUBNETS_CIDR = Parameter(PUBLIC_SUBNETS_CIDR_T, Type="CommaDelimitedList")
PUBLIC_SUBNETS_T = "PublicSubnets"
PUBLIC_SUBNETS = Parameter(PUBLIC_SUBNETS_T, Type=SUBNETS_TYPE)

APP_SUBNETS_CIDR_T = "AppSubnetsCidr"
APP_SUBNETS_CIDR = Parameter(APP_SUBNETS_CIDR_T, Type="CommaDelimitedList")
APP_SUBNETS_T = "AppSubnets"
APP_SUBNETS = Parameter(APP_SUBNETS_T, Type=SUBNETS_TYPE)

USE_SUB_ZONE_T = "UseSubDnsZone"
USE_SUB_ZONE = Parameter(
    USE_SUB_ZONE_T, Type="String", AllowedValues=["True", "False"], Default="True"
)
