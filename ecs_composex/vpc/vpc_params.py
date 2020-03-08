# -*- coding: utf-8 -*-
"""
Parameters related to the VPC settings. Used by ecs_composex.vpc and others
"""

from troposphere import Parameter, Sub, ImportValue
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T


VPC_TYPE = 'AWS::EC2::VPC::Id'
AMI_TYPE = 'AWS::EC2::Image::Id'
SUBNET_TYPE = 'AWS::EC2::Subnet::Id'
SUBNETS_TYPE = 'List<AWS::EC2::Subnet::Id>'
R53_TYPE = 'AWS::Route53::HostedZone::Id'
AZS_TYPE = 'List<AWS::EC2::AvailabilityZone::Name>'
SG_ID_TYPE = 'AWS::EC2::SecurityGroup::Id'
SG_NAME_TYPE = 'AWS::EC2::SecurityGroup::GroupName'


VPC_ID_T = 'VpcId'
VPC_ID = Parameter(
    VPC_ID_T, Type=VPC_TYPE
)

STORAGE_SUBNETS_CIDR_T = 'StorageSubnetsCidr'
STORAGE_SUBNETS_CIDR = Parameter(
    STORAGE_SUBNETS_CIDR_T,
    Type='CommaDelimitedList'
)
STORAGE_SUBNETS_T = 'StorageSubnets'
STORAGE_SUBNETS = Parameter(STORAGE_SUBNETS_T, Type=SUBNETS_TYPE)

BACKEND_SUBNETS_CIDR_T = 'BackendSubnetsCidr'
BACKEND_SUBNETS_CIDR = Parameter(
    BACKEND_SUBNETS_CIDR_T,
    Type='CommaDelimitedList'
)
BACKEND_SUBNETS_T = 'BackendSubnets'
BACKEND_SUBNETS = Parameter(BACKEND_SUBNETS_T, Type=SUBNETS_TYPE)

PUBLIC_SUBNETS_CIDR_T = 'PublicSubnetsCidr'
PUBLIC_SUBNETS_CIDR = Parameter(
    PUBLIC_SUBNETS_CIDR_T,
    Type='CommaDelimitedList'
)
PUBLIC_SUBNETS_T = 'PublicSubnets'
PUBLIC_SUBNETS = Parameter(PUBLIC_SUBNETS_T, Type=SUBNETS_TYPE)

APP_SUBNETS_CIDR_T = 'AppSubnetsCidr'
APP_SUBNETS_CIDR = Parameter(
    APP_SUBNETS_CIDR_T,
    Type='CommaDelimitedList'
)
APP_SUBNETS_T = 'AppSubnets'
APP_SUBNETS = Parameter(APP_SUBNETS_T, Type=SUBNETS_TYPE)

USE_SUB_ZONE_T = 'UseSubDnsZone'
USE_SUB_ZONE = Parameter(
    USE_SUB_ZONE_T, Type='String',
    AllowedValues=['True', 'False'],
    Default='True'
)

VPC_MAP_ID_T = 'VpcDiscoveryMapId'
VPC_MAP_ID = Parameter(
    VPC_MAP_ID_T,
    Type='String',
    Default='<none>'
)

VPC_MAP_ARN_T = 'VpcDiscoveryMapArn'
VPC_MAP_ARN = Parameter(
    VPC_MAP_ARN_T,
    Type='String',
    Default='<none>'
)

VPC_DNS_ZONE_T = 'VpcDnsZoneName'
VPC_DNS_ZONE = Parameter(
    VPC_DNS_ZONE_T,
    Type='String', Default='cluster.local'
)

VPC_ID_IMPORT = ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{VPC_ID_T}"))
APP_SUBNETS_IMPORT = ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{APP_SUBNETS_T}"))
PUBLIC_SUBNETS_IMPORT = ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{PUBLIC_SUBNETS_T}"))
STORAGE_SUBNETS_IMPORT = ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{STORAGE_SUBNETS_T}"))
NAMESPACE_ID_IMPORT = ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{VPC_MAP_ID_T}"))
NAMESPACE_ARN_IMPORT = ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{VPC_MAP_ARN_T}"))

APP_SUBNETS_CIDR_IMPORT = ImportValue(Sub(f"${{{ROOT_STACK_NAME_T}}}-{APP_SUBNETS_CIDR_T}"))
