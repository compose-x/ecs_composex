# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Parameters related to the VPC settings. Used by ecs_composex.vpc and others
"""

from ecs_composex.common.cfn_params import Parameter

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

VPC_SETTINGS = "VPC Settings"


VPC_T = "Vpc"
IGW_T = "InternetGatewayV4"

RES_KEY = "x-vpc"
MOD_KEY = "vpc"
VPC_ID_T = "VpcId"
VPC_ID = Parameter(VPC_ID_T, group_label=VPC_SETTINGS, Type=VPC_TYPE)

VPC_CIDR_T = "VpcCidr"
VPC_CIDR = Parameter(
    VPC_CIDR_T, group_label=VPC_SETTINGS, Type="String", Default=DEFAULT_VPC_CIDR
)

VPC_SINGLE_NAT_T = "SingleNat"
VPC_SINGLE_NAT = Parameter(
    VPC_SINGLE_NAT_T, group_label=VPC_SETTINGS, Type="String", Default="True"
)

STORAGE_SUBNETS_CIDR_T = "StorageSubnetsCidr"
STORAGE_SUBNETS_CIDR = Parameter(
    STORAGE_SUBNETS_CIDR_T, group_label=VPC_SETTINGS, Type="CommaDelimitedList"
)
STORAGE_SUBNETS_T = "StorageSubnets"
STORAGE_SUBNETS = Parameter(
    STORAGE_SUBNETS_T, group_label=VPC_SETTINGS, Type=SUBNETS_TYPE
)

BACKEND_SUBNETS_CIDR_T = "BackendSubnetsCidr"
BACKEND_SUBNETS_CIDR = Parameter(
    BACKEND_SUBNETS_CIDR_T, group_label=VPC_SETTINGS, Type="CommaDelimitedList"
)
BACKEND_SUBNETS_T = "BackendSubnets"
BACKEND_SUBNETS = Parameter(
    BACKEND_SUBNETS_T, group_label=VPC_SETTINGS, Type=SUBNETS_TYPE
)

PUBLIC_SUBNETS_CIDR_T = "PublicSubnetsCidr"
PUBLIC_SUBNETS_CIDR = Parameter(PUBLIC_SUBNETS_CIDR_T, Type="CommaDelimitedList")
PUBLIC_SUBNETS_T = "PublicSubnets"
PUBLIC_SUBNETS = Parameter(
    PUBLIC_SUBNETS_T, group_label=VPC_SETTINGS, Type=SUBNETS_TYPE
)

APP_SUBNETS_CIDR_T = "AppSubnetsCidr"
APP_SUBNETS_CIDR = Parameter(
    APP_SUBNETS_CIDR_T,
    group_label=VPC_SETTINGS,
    Type="CommaDelimitedList",
)
APP_SUBNETS_T = "AppSubnets"
APP_SUBNETS = Parameter(APP_SUBNETS_T, group_label=VPC_SETTINGS, Type=SUBNETS_TYPE)
