# -*- coding: utf-8 -*-

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

from string import ascii_lowercase as alpha
from troposphere.ec2 import (
    Subnet, SubnetRouteTableAssociation,
    NatGateway, EIP, Route, RouteTable
)
from troposphere import (
    GetAtt, Tags, Ref, Sub, If
)

from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T


def add_storage_subnets(template, vpc, az_range, layers):
    """
    Function to add storage subnets inside the VPC

    :param template: VPC Template()
    :param vpc: Vpc() for Ref()
    :param az_range: range for iteration over select AZs

    :returns: tuple() list of rtb, list of subnets
    """
    rtb = RouteTable(
        'StorageRtb',
        template=template,
        VpcId=Ref(vpc),
        Tags=Tags(Name='StorageRtb') + Tags({'vpc:usage': 'storage'})
    )

    subnets = []
    for count, subnet_cidr in zip(az_range, layers['stor']):
        subnet = Subnet(
            f'StorageSubnet{alpha[count].upper()}',
            template=template,
            CidrBlock=subnet_cidr,
            VpcId=Ref(vpc),
            AvailabilityZone=Sub(f'${{AWS::Region}}{alpha[count]}'),
            Tags=Tags(
                Name=If(
                    USE_STACK_NAME_CON_T,
                    Sub(f'${{AWS::StackName}}-Storage-{alpha[count]}'),
                    Sub(f'${{{ROOT_STACK_NAME_T}}}-Storage-{alpha[count]}')
                ),
            ) + Tags({'vpc:usage': 'storage'})
        )
        SubnetRouteTableAssociation(
            f'StorageSubnetAssoc{alpha[count].upper()}',
            template=template,
            SubnetId=Ref(subnet),
            RouteTableId=Ref(rtb)
        )
        subnets.append(subnet)
    return ([rtb], subnets)


def add_public_subnets(template, vpc, az_range, layers, igw, single_nat):
    """
    Function to add public subnets for the VPC

    :param template: VPC Template()
    :param vpc: Vpc() for Ref()
    :param az_range: range for iteration over select AZs

    :returns: tuple() list of rtb, list of subnets, list of nats
    """
    rtb = RouteTable(
        'PublicRtb',
        template=template,
        VpcId=Ref(vpc),
        Tags=Tags(Name='PublicRtb') + Tags({'vpc:usage': 'public'})
    )
    Route(
        'PublicDefaultRoute',
        template=template,
        GatewayId=Ref(igw),
        RouteTableId=Ref(rtb),
        DestinationCidrBlock='0.0.0.0/0'
    )
    subnets = []
    nats = []
    for count, subnet_cidr in zip(az_range, layers['pub']):
        subnet = Subnet(
            f'PublicSubnet{alpha[count].upper()}',
            template=template,
            CidrBlock=subnet_cidr,
            VpcId=Ref(vpc),
            AvailabilityZone=Sub(f'${{AWS::Region}}{alpha[count]}'),
            MapPublicIpOnLaunch=True,
            Tags=Tags(
                Name=If(
                    USE_STACK_NAME_CON_T,
                    Sub(f'${{AWS::StackName}}-Public-{alpha[count]}'),
                    Sub(f'${{{ROOT_STACK_NAME_T}}}-Public-{alpha[count]}')
                ),
            ) + Tags({'30-automation:usage': 'public'})
        )
        if (single_nat and not nats) or not single_nat:
            eip = EIP(
                f"NatGatewayEip{alpha[count].upper()}",
                template=template,
                Domain='vpc'
            )
            nat = NatGateway(
                f"NatGatewayAz{alpha[count].upper()}",
                template=template,
                AllocationId=GetAtt(eip, 'AllocationId'),
                SubnetId=Ref(subnet)
                )
            nats.append(nat)
        SubnetRouteTableAssociation(
            f'PublicSubnetsRtbAssoc{alpha[count].upper()}',
            template=template,
            RouteTableId=Ref(rtb),
            SubnetId=Ref(subnet)
        )
        subnets.append(subnet)
    return ([rtb], subnets, nats)


def add_apps_subnets(template, vpc, az_range, layers, nats):
    """
    Function to add application/hosts subnets to the VPC

    :param template: VPC Template()
    :param vpc: Vpc() for Ref()
    :param az_range: range for iteration over select AZs
    :param nats: list of NatGateway()

    :returns: tuple() list of rtb, list of subnets
    """
    subnets = []
    rtbs = []
    if len(nats) < len(az_range):
        primary_nat = nats[0]
        nats = []
        for az in az_range:
            nats.append(primary_nat)
    for count, subnet_cidr, nat in zip(az_range, layers['app'], nats):
        suffix = alpha[count].upper()
        subnet = Subnet(
            f'AppSubnet{suffix}',
            template=template,
            CidrBlock=subnet_cidr,
            VpcId=Ref(vpc),
            AvailabilityZone=Sub(f'${{AWS::Region}}{alpha[count]}'),
            Tags=Tags(
                Name=If(
                    USE_STACK_NAME_CON_T,
                    Sub(f'${{AWS::StackName}}-App-{alpha[count]}'),
                    Sub(f'${{{ROOT_STACK_NAME_T}}}-App-{alpha[count]}')
                ),
            ) + Tags({'vpc:usage': 'application'})
        )
        rtb = RouteTable(
            f'AppRtb{alpha[count].upper()}',
            template=template,
            VpcId=Ref(vpc),
            Tags=Tags(Name=f'AppRtb{alpha[count].upper()}')
        )
        Route(
            f'AppRoute{alpha[count].upper()}',
            template=template,
            NatGatewayId=Ref(nat),
            RouteTableId=Ref(rtb),
            DestinationCidrBlock='0.0.0.0/0'
        )
        SubnetRouteTableAssociation(
            f'SubnetRtbAssoc{alpha[count].upper()}',
            template=template,
            RouteTableId=Ref(rtb),
            SubnetId=Ref(subnet)
        )
        rtbs.append(rtb)
        subnets.append(subnet)
    return rtbs, subnets
