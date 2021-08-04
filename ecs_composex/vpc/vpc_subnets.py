#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

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

from math import ceil, log

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, If, Ref, Sub, Tags
from troposphere.ec2 import (
    EIP,
    Entry,
    NatGateway,
    PrefixList,
    Route,
    RouteTable,
    SecurityGroup,
    SecurityGroupRule,
    Subnet,
    SubnetRouteTableAssociation,
    VPCEndpoint,
)

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.vpc import metadata
from ecs_composex.vpc.vpc_params import VPC_T


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
        Metadata=metadata,
    )

    subnets = []
    entries = []
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
            Metadata=metadata,
        )
        SubnetRouteTableAssociation(
            f"StorageSubnetAssoc{index.upper()}",
            template=template,
            SubnetId=Ref(subnet),
            RouteTableId=Ref(rtb),
            Metadata=metadata,
        )
        subnets.append(subnet)
        entries.append(
            Entry(
                Cidr=subnet_cidr,
                Description=Sub(f"storage-{index} -- ${{{vpc.title}}}"),
            )
        )
    template.add_resource(
        PrefixList(
            "StorageSubnetsPrefixList",
            AddressFamily="IPv4",
            Entries=entries,
            MaxEntries=int((pow(2, ceil(log(len(entries), 2)))) * 2),
            PrefixListName=Sub(f"${{{vpc.title}}}-storage-subnets"),
        )
    )
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
        Metadata=metadata,
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
    entries = []
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
            Metadata=metadata,
        )
        if (single_nat and not nats) or not single_nat:
            eip = EIP(f"NatGatewayEip{index.upper()}", template=template, Domain="vpc")
            nat = NatGateway(
                f"NatGatewayAz{index.upper()}",
                template=template,
                AllocationId=GetAtt(eip, "AllocationId"),
                SubnetId=Ref(subnet),
                Metadata=metadata,
            )
            nats.append(nat)
        SubnetRouteTableAssociation(
            f"PublicSubnetsRtbAssoc{index.upper()}",
            template=template,
            RouteTableId=Ref(rtb),
            SubnetId=Ref(subnet),
        )
        subnets.append(subnet)
        entries.append(
            Entry(
                Cidr=subnet_cidr, Description=Sub(f"public-{index} -- ${{{vpc.title}}}")
            )
        )
    template.add_resource(
        PrefixList(
            "PublicSubnetsPrefixList",
            AddressFamily="IPv4",
            Entries=entries,
            MaxEntries=int((pow(2, ceil(log(len(entries), 2)))) * 2),
            PrefixListName=Sub(f"${{{vpc.title}}}-public-subnets"),
        )
    )
    return [rtb], subnets, nats


def add_gateway_endpoint(service, rtbs, template):
    """
    Function to add a service endpoint for gateways
    """
    VPCEndpoint(
        NONALPHANUM.sub("", f"{service['service']}Endpoint"),
        template=template,
        ServiceName=Sub(f"com.amazonaws.${{AWS::Region}}.{service['service']}"),
        RouteTableIds=[Ref(rtb) for rtb in rtbs],
        VpcEndpointType="Gateway",
        VpcId=Ref(template.resources[VPC_T]),
    )


def add_interface_endpoint(sg, service, subnets, template):
    """
    Function to add a service endpoint for gateways
    """
    VPCEndpoint(
        NONALPHANUM.sub("", f"{service['service']}Endpoint"),
        template=template,
        ServiceName=Sub(f"com.amazonaws.${{AWS::Region}}.{service['service']}"),
        SubnetIds=[Ref(subnet) for subnet in subnets],
        VpcEndpointType="Interface",
        VpcId=Ref(template.resources[VPC_T]),
        SecurityGroupIds=[Ref(sg)],
        PrivateDnsEnabled=True,
    )


def add_apps_subnets(template, vpc, az_index, layers, nats, endpoints=None):
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
    entries = []
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
            Metadata=metadata,
        )
        rtb = RouteTable(
            f"AppRtb{index.upper()}",
            template=template,
            VpcId=Ref(vpc),
            Tags=Tags(Name=f"AppRtb{index.upper()}"),
            Metadata=metadata,
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
            Metadata=metadata,
        )
        rtbs.append(rtb)
        subnets.append(subnet)
        entries.append(
            Entry(
                Cidr=subnet_cidr, Description=Sub(f"apps-{index} -- ${{{vpc.title}}}")
            )
        )
    if endpoints is not None and keyisset("AwsServices", endpoints):
        sg_endpoints = SecurityGroup(
            "VpcEndpointsSg",
            template=template,
            GroupName=Sub(f"vpc-endpoints-${{{VPC_T}}}"),
            GroupDescription=Sub(f"VPC Endpoints for VPC ${{{VPC_T}}}"),
            VpcId=Ref(template.resources[VPC_T]),
            SecurityGroupIngress=[
                SecurityGroupRule(
                    CidrIp=GetAtt(template.resources[VPC_T], "CidrBlock"),
                    FromPort=443,
                    ToPort=443,
                    IpProtocol="TCP",
                    Description="HTTPs to VPC Endpoint",
                )
            ],
        )
        for service in endpoints["AwsServices"]:
            if service["service"] == "s3":
                add_gateway_endpoint(service, rtbs, template)
            else:
                add_interface_endpoint(sg_endpoints, service, subnets, template)

    template.add_resource(
        PrefixList(
            "AppsSubnetsPrefixList",
            AddressFamily="IPv4",
            Entries=entries,
            MaxEntries=int((pow(2, ceil(log(len(entries), 2)))) * 2),
            PrefixListName=Sub(f"${{{vpc.title}}}-apps-subnets"),
        )
    )
    return rtbs, subnets
