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
Functions to add the three VPC layer type subnets:

* Storage
* Public
* App

RTB -> Route Table

Storage subnet type : All subnets use the same RTB, no route to 0.0.0.0/0
Public subnet type: All subnets use the same RTB, route to 0.0.0.0/0 via InternetGateway
App subnet type: Each subnet has its own RTB, each RTB points to a different NAT Gateway in its
respective AZ

"""

from troposphere import GetAtt, Tags, Ref, Sub, If
from troposphere.ec2 import (
    Subnet,
    SubnetRouteTableAssociation,
    NatGateway,
    EIP,
    Route,
    RouteTable,
)

from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM


def add_storage_subnets(template, vpc, az_index, layers):
    """
    Function to add storage subnets inside the VPC

    :param layers: VPC layers
    :type layers: dict
    :param template: VPC Template()
    :type template: troposphere.Template
    :param vpc: Vpc() for Ref()
    :type vpc: troposphere.ec2.Vpc
    :param az_index: List of AZ Index (a,b,c..)
    :type az_index: list

    :returns: tuple() list of rtb, list of subnets
    """
    rtb = RouteTable(
        "StorageRtb",
        template=template,
        VpcId=Ref(vpc),
        Tags=Tags(Name="StorageRtb") + Tags({f"vpc{DELIM}usage": "storage"}),
    )

    subnets = []
    for index, subnet_cidr in zip(az_index, layers["stor"]):
        subnet = Subnet(
            f"StorageSubnet{index.upper()}",
            template=template,
            CidrBlock=subnet_cidr,
            VpcId=Ref(vpc),
            AvailabilityZone=Sub(f"${{AWS::Region}}{index}"),
            Tags=Tags(
                Name=If(
                    USE_STACK_NAME_CON_T,
                    Sub(f"${{AWS::StackName}}-Storage-{index}"),
                    Sub(f"${{{ROOT_STACK_NAME_T}}}-Storage-{index}"),
                ),
            )
            + Tags({f"vpc{DELIM}usage": "storage", f"vpc{DELIM}vpc-id": Ref(vpc)}),
        )
        SubnetRouteTableAssociation(
            f"StorageSubnetAssoc{index.upper()}",
            template=template,
            SubnetId=Ref(subnet),
            RouteTableId=Ref(rtb),
        )
        subnets.append(subnet)
    return [rtb], subnets


def add_public_subnets(template, vpc, az_index, layers, igw, single_nat):
    """
    Function to add public subnets for the VPC

    :param layers: layers of subnets
    :type layers: dict
    :param igw: internet gateway to route to
    :type igw: troposphere.ec2.InternetGateway
    :param single_nat: whether we should have a single NAT Gateway
    :type single_nat: boolean
    :param template: VPC Template()
    :type template: troposphere.Template
    :param vpc: Vpc() for Ref()
    :type vpc: troposphere.ec2.Template
    :param az_range: range for iteration over select AZs
    :type az_range: list

    :return: tuple() list of rtb, list of subnets, list of nats
    """
    rtb = RouteTable(
        "PublicRtb",
        template=template,
        VpcId=Ref(vpc),
        Tags=Tags(Name="PublicRtb") + Tags({f"vpc{DELIM}usage": "public"}),
    )
    Route(
        "PublicDefaultRoute",
        template=template,
        GatewayId=Ref(igw),
        RouteTableId=Ref(rtb),
        DestinationCidrBlock="0.0.0.0/0",
    )
    subnets = []
    nats = []
    for index, subnet_cidr in zip(az_index, layers["pub"]):
        subnet = Subnet(
            f"PublicSubnet{index.upper()}",
            template=template,
            CidrBlock=subnet_cidr,
            VpcId=Ref(vpc),
            AvailabilityZone=Sub(f"${{AWS::Region}}{index}"),
            MapPublicIpOnLaunch=True,
            Tags=Tags(
                Name=If(
                    USE_STACK_NAME_CON_T,
                    Sub(f"${{AWS::StackName}}-Public-{index}"),
                    Sub(f"${{{ROOT_STACK_NAME_T}}}-Public-{index}"),
                ),
            )
            + Tags({f"vpc{DELIM}usage": "public", f"vpc{DELIM}vpc-id": Ref(vpc)}),
        )
        if (single_nat and not nats) or not single_nat:
            eip = EIP(f"NatGatewayEip{index.upper()}", template=template, Domain="vpc")
            nat = NatGateway(
                f"NatGatewayAz{index.upper()}",
                template=template,
                AllocationId=GetAtt(eip, "AllocationId"),
                SubnetId=Ref(subnet),
            )
            nats.append(nat)
        SubnetRouteTableAssociation(
            f"PublicSubnetsRtbAssoc{index.upper()}",
            template=template,
            RouteTableId=Ref(rtb),
            SubnetId=Ref(subnet),
        )
        subnets.append(subnet)
    return [rtb], subnets, nats


def add_apps_subnets(template, vpc, az_index, layers, nats):
    """
    Function to add application/hosts subnets to the VPC

    :param template: VPC Template()
    :param vpc: Vpc() for Ref()
    :param list az_index: index for the AZ (a,b,c ..)
    :param nats: list of NatGateway()

    :returns: tuple() list of rtb, list of subnets
    """
    subnets = []
    rtbs = []
    if len(nats) < len(az_index):
        primary_nat = nats[0]
        nats = []
        for _ in az_index:
            nats.append(primary_nat)
    for index, subnet_cidr, nat in zip(az_index, layers["app"], nats):
        suffix = index.upper()
        subnet = Subnet(
            f"AppSubnet{suffix}",
            template=template,
            CidrBlock=subnet_cidr,
            VpcId=Ref(vpc),
            AvailabilityZone=Sub(f"${{AWS::Region}}{index}"),
            Tags=Tags(
                Name=If(
                    USE_STACK_NAME_CON_T,
                    Sub(f"${{AWS::StackName}}-App-{index}"),
                    Sub(f"${{{ROOT_STACK_NAME_T}}}-App-{index}"),
                ),
            )
            + Tags({f"vpc{DELIM}usage": "application", f"vpc{DELIM}vpc-id": Ref(vpc)}),
        )
        rtb = RouteTable(
            f"AppRtb{index.upper()}",
            template=template,
            VpcId=Ref(vpc),
            Tags=Tags(Name=f"AppRtb{index.upper()}"),
        )
        Route(
            f"AppRoute{index.upper()}",
            template=template,
            NatGatewayId=Ref(nat),
            RouteTableId=Ref(rtb),
            DestinationCidrBlock="0.0.0.0/0",
        )
        SubnetRouteTableAssociation(
            f"SubnetRtbAssoc{index.upper()}",
            template=template,
            RouteTableId=Ref(rtb),
            SubnetId=Ref(subnet),
        )
        rtbs.append(rtb)
        subnets.append(subnet)
    return rtbs, subnets
