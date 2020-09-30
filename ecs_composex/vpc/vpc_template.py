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
Create the VPC template and its associated resources
TODO : Implement VPC Endpoints, NetworkACLs, VPC Flow logging to S3.
"""

import re

from troposphere import Tags, Join, Ref, Sub, If
from troposphere.ec2 import (
    VPC as VPCType,
    VPCGatewayAttachment,
    InternetGateway,
    DHCPOptions,
    VPCDHCPOptionsAssociation,
)

from ecs_composex.common import build_template, LOG
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.dns.dns_params import PRIVATE_DNS_ZONE_NAME
from ecs_composex.vpc import vpc_params, aws_mappings
from ecs_composex.vpc.vpc_params import VPC_T, IGW_T
from ecs_composex.vpc.vpc_maths import get_subnet_layers
from ecs_composex.vpc.vpc_subnets import (
    add_public_subnets,
    add_storage_subnets,
    add_apps_subnets,
)
from ecs_composex.vpc import metadata

AZ_INDEX_PATTERN = r"(([a-z0-9-]+)([a-z]{1}$))"
AZ_INDEX_RE = re.compile(AZ_INDEX_PATTERN)


def add_template_outputs(template, vpc, storage_subnets, public_subnets, app_subnets):
    """
    Function to add outputs / exports to the template

    :param template: VPC Template()
    :param vpc: Vpc() for Ref()
    :param storage_subnets: List of Subnet()
    :param public_subnets: List of Subnet()
    :param app_subnets: List of Subnet()
    """
    template.add_output(
        ComposeXOutput(
            vpc,
            [
                (vpc_params.VPC_ID_T, vpc_params.VPC_ID_T, Ref(vpc)),
                (
                    vpc_params.STORAGE_SUBNETS_T,
                    vpc_params.STORAGE_SUBNETS_T,
                    Join(",", [Ref(subnet) for subnet in storage_subnets]),
                ),
                (
                    vpc_params.PUBLIC_SUBNETS_T,
                    vpc_params.PUBLIC_SUBNETS_T,
                    Join(",", [Ref(subnet) for subnet in public_subnets]),
                ),
                (
                    vpc_params.APP_SUBNETS_T,
                    vpc_params.APP_SUBNETS_T,
                    Join(",", [Ref(subnet) for subnet in app_subnets]),
                ),
            ],
            duplicate_attr=True,
        ).outputs
    )


def add_vpc_cidrs_outputs(template, vpc, layers):
    """
    Function to add outputs / exports to the template

    :param template: VPC Template()
    :type template: troposphere.Template
    :param layers: dict of layers CIDRs to export
    :type layers: dict
    """
    template.add_output(
        ComposeXOutput(
            vpc,
            [
                (
                    vpc_params.STORAGE_SUBNETS_CIDR_T,
                    vpc_params.STORAGE_SUBNETS_CIDR_T,
                    Join(",", [cidr for cidr in layers["stor"]]),
                ),
                (
                    vpc_params.PUBLIC_SUBNETS_CIDR_T,
                    vpc_params.PUBLIC_SUBNETS_CIDR_T,
                    Join(",", [cidr for cidr in layers["pub"]]),
                ),
                (
                    vpc_params.APP_SUBNETS_CIDR_T,
                    vpc_params.APP_SUBNETS_CIDR_T,
                    Join(",", [cidr for cidr in layers["app"]]),
                ),
            ],
            duplicate_attr=True,
        ).outputs
    )


def add_vpc_core(template, vpc_cidr):
    """
    Function to create the core resources of the VPC
    and add them to the core VPC template

    :param template: VPC Template()
    :param vpc_cidr: str of the VPC CIDR i.e. 192.168.0.0/24

    :return: tuple() with the vpc and igw object
    """
    vpc = VPCType(
        VPC_T,
        template=template,
        CidrBlock=vpc_cidr,
        EnableDnsHostnames=True,
        EnableDnsSupport=True,
        Tags=Tags(
            Name=If(USE_STACK_NAME_CON_T, Ref("AWS::StackName"), Ref(ROOT_STACK_NAME)),
            EnvironmentName=If(
                USE_STACK_NAME_CON_T, Ref("AWS::StackName"), Ref(ROOT_STACK_NAME)
            ),
        ),
        Metadata=metadata,
    )
    igw = InternetGateway(IGW_T, template=template)
    VPCGatewayAttachment(
        "VPCGatewayAttachement",
        template=template,
        InternetGatewayId=Ref(igw),
        VpcId=Ref(vpc),
        Metadata=metadata,
    )
    dhcp_opts = DHCPOptions(
        "VpcDhcpOptions",
        template=template,
        DomainName=If(
            USE_STACK_NAME_CON_T,
            Sub(
                f"svc.${{AWS::StackName}}.${{{PRIVATE_DNS_ZONE_NAME.title}}} "
                f"${{AWS::StackName}}.${{{PRIVATE_DNS_ZONE_NAME.title}}}"
            ),
            Sub(
                f"svc.${{{ROOT_STACK_NAME_T}}}.${{{PRIVATE_DNS_ZONE_NAME.title}}} "
                f"${{{ROOT_STACK_NAME_T}}}.${{{PRIVATE_DNS_ZONE_NAME.title}}}"
            ),
        ),
        DomainNameServers=["AmazonProvidedDNS"],
        Tags=Tags(Name=Sub(f"dhcp-${{{vpc.title}}}")),
        Metadata=metadata,
    )
    VPCDHCPOptionsAssociation(
        "VpcDhcpOptionsAssociate",
        template=template,
        DhcpOptionsId=Ref(dhcp_opts),
        VpcId=Ref(vpc),
        Metadata=metadata,
    )
    return (vpc, igw)


def generate_vpc_template(cidr_block, azs, endpoints=None, single_nat=False):
    """
    Function to generate a new VPC template for CFN

    :param cidr_block: str of the CIDR used for this VPC
    :param azs: list of AWS Azs i.e. ['eu-west-1a', 'eu-west-1b']
    :param single_nat: True/False if you want a single NAT for the Application Subnets
    :type single_nat: bool

    :return: Template() representing the VPC and associated resources
    """
    if endpoints is None:
        endpoints = []
    curated_azs = []
    for az in azs:
        if isinstance(az, dict):
            curated_azs.append(az["ZoneName"])
        elif isinstance(az, str):
            curated_azs.append(az)
    azs_index = [AZ_INDEX_RE.match(az).groups()[-1] for az in curated_azs]
    layers = get_subnet_layers(cidr_block, len(curated_azs))
    template = build_template(
        "VpcTemplate generated via ECS Compose X",
        [PRIVATE_DNS_ZONE_NAME],
    )
    LOG.debug(azs_index)
    template.add_mapping("AwsLbAccounts", aws_mappings.AWS_LB_ACCOUNTS)
    vpc = add_vpc_core(template, cidr_block)
    storage_subnets = add_storage_subnets(template, vpc[0], azs_index, layers)
    public_subnets = add_public_subnets(
        template, vpc[0], azs_index, layers, vpc[-1], single_nat
    )
    app_subnets = add_apps_subnets(
        template, vpc[0], azs_index, layers, public_subnets[-1], endpoints
    )
    add_template_outputs(
        template,
        vpc[0],
        storage_subnets[1],
        public_subnets[1],
        app_subnets[1],
    )
    add_vpc_cidrs_outputs(template, vpc[0], layers)
    return template
