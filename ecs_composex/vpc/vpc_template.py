#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Create the VPC template and its associated resources
"""

import re

from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    GetAtt,
    If,
    Join,
    Ref,
    Sub,
    Tags,
)
from troposphere.ec2 import VPC as VPCType
from troposphere.ec2 import (
    DHCPOptions,
    Entry,
    FlowLog,
    InternetGateway,
    PrefixList,
    VPCDHCPOptionsAssociation,
    VPCGatewayAttachment,
)
from troposphere.iam import Policy, Role
from troposphere.logs import LogGroup

from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.dns.dns_params import PRIVATE_DNS_ZONE_NAME
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.vpc import metadata, vpc_params
from ecs_composex.vpc.vpc_params import IGW_T, VPC_T

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
    template.add_resource(
        PrefixList(
            "VpcPrefixList",
            AddressFamily="IPv4",
            Entries=[
                Entry(
                    Cidr=vpc_cidr, Description=Sub(f"Primary CIDR for ${{{vpc.title}}}")
                )
            ],
            MaxEntries=5,
            PrefixListName=Ref(vpc),
        )
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
    return vpc, igw


def add_vpc_flow(template, vpc, boundary=None):
    """
    Function to add VPC Flow Log to log VPC

    :param troposphere.Template template:
    :param vpc: The VPC Object
    :param str boundary:
    """
    if boundary and boundary.startswith("arn:aws"):
        perm_boundary = boundary
    elif boundary and not boundary.startswith("arn:aws"):
        perm_boundary = Sub(
            f"arn:${{{AWS_PARTITION}}}:iam:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:policy/{boundary}"
        )
    else:
        perm_boundary = Ref(AWS_NO_VALUE)
    log_group = template.add_resource(
        LogGroup(
            "FlowLogsGroup",
            RetentionInDays=14,
            LogGroupName=Sub(f"flowlogs/vpc/${{{vpc.title}}}"),
        )
    )
    role = template.add_resource(
        Role(
            "FlowLogsRole",
            AssumeRolePolicyDocument=service_role_trust_policy("ec2"),
            PermissionsBoundary=perm_boundary,
            Policies=[
                Policy(
                    PolicyName="CloudWatchAccess",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                                "Effect": "Allow",
                                "Action": [
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                ],
                                "Resource": GetAtt(log_group, "Arn"),
                            }
                        ],
                    },
                )
            ],
        )
    )
    template.add_resource(
        FlowLog(
            "VpcFlowLogs",
            DeliverLogsPermissionArn=GetAtt(role, "Arn"),
            LogGroupName=Ref(log_group),
            LogDestinationType="cloud-watch-logs",
            MaxAggregationInterval=600,
            ResourceId=Ref(vpc),
            ResourceType="VPC",
            TrafficType="ALL",
        )
    )
