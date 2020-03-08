# -*- coding: utf-8 -*-

"""
Create the VPC template and its associated resources
TODO : Implement VPC Endpoints, NetworkACLs, VPC Flow logging to S3.
"""

import boto3
from troposphere import (
    GetAtt, Tags,
    Join, Ref, Sub, If
)
from troposphere.ec2 import (
    VPC as VPCType, VPCGatewayAttachment,
    InternetGateway,
    DHCPOptions, VPCDHCPOptionsAssociation
)
from troposphere.route53 import HostedZoneVPCs, HostedZone
from troposphere.servicediscovery import PrivateDnsNamespace as VpcSpace

from ecs_composex.common import (
    cfn_params,
    cfn_conditions,
    build_template
)
from ecs_composex.common.cfn_conditions import (
    USE_CLOUDMAP_CON_T,
    USE_STACK_NAME_CON_T
)
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME,
    ROOT_STACK_NAME_T
)
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.common.templates import validate_template
from ecs_composex.vpc import (
    vpc_params, aws_mappings, vpc_conditions
)
from ecs_composex.vpc.vpc_maths import get_subnet_layers
from ecs_composex.vpc.vpc_subnets import (
    add_public_subnets,
    add_storage_subnets,
    add_apps_subnets
)

VPC_T = 'Vpc'
IGW_T = 'InternetGatewayV4'


def add_cloudmap_support(template, vpc):
    """
    Function add a VPC CloudMap instance

    :param template: VPC Template()
    :param vpc: Vpc() object for Ref()

    :returns: NIL
    """
    map_id = VpcSpace(
        'VpcCloudMapNameSpace',
        Condition=USE_CLOUDMAP_CON_T,
        template=template,
        Description=Sub(f"Map for VPC ${{{vpc.title}}}"),
        Vpc=Ref(vpc),
        Name=If(
            USE_STACK_NAME_CON_T,
            Sub(f'${{AWS::StackName}}.${{{vpc_params.VPC_DNS_ZONE_T}}}'),
            Sub(f'${{{ROOT_STACK_NAME_T}}}.${{{vpc_params.VPC_DNS_ZONE_T}}}')
        )
    )
    template.add_output(
        formatted_outputs(
            [
                {vpc_params.VPC_MAP_ID_T: GetAtt(map_id, 'Id')},
                {vpc_params.VPC_MAP_ARN_T: GetAtt(map_id, 'Arn')}
            ],
            export=True
        )
    )


def add_template_outputs(template, vpc, storage_subnets, public_subnets, app_subnets):
    """
    Function to add outputs / exports to the template

    :param template: VPC Template()
    :param vpc: Vpc() for Ref()
    :param storage_subnets: List of Subnet()
    :param public_subnets: List of Subnet()
    :param app_subnets: List of Subnet()

    :returns: NIL
    """
    template.add_output(formatted_outputs(
        [
            {vpc_params.VPC_ID_T: Ref(vpc)},
            {
                vpc_params.STORAGE_SUBNETS_T: Join(
                    ',', [Ref(subnet) for subnet in storage_subnets]
                )
            },
            {
                vpc_params.PUBLIC_SUBNETS_T: Join(
                    ',', [Ref(subnet) for subnet in public_subnets]
                )
            },
            {
                vpc_params.APP_SUBNETS_T: Join(
                    ',', [Ref(subnet) for subnet in app_subnets]
                )
            }
        ],
        export=True
    ))


def add_vpc_cidrs_outputs(template, layers):
    """
    Function to add outputs / exports to the template

    :param template: VPC Template()
    :type template: troposphere.Template
    :param layers: dict of layers CIDRs to export
    :type layers: dict
    """
    template.add_output(formatted_outputs(
        [
            {
                vpc_params.STORAGE_SUBNETS_CIDR_T: Join(
                    ',', [cidr for cidr in layers['stor']]
                )
            },
            {
                vpc_params.PUBLIC_SUBNETS_CIDR_T: Join(
                    ',', [cidr for cidr in layers['pub']]
                )
            },
            {
                vpc_params.APP_SUBNETS_CIDR_T: Join(
                    ',', [cidr for cidr in layers['app']]
                )
            }
        ],
        export=True
    ))


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
            Name=If(
                USE_STACK_NAME_CON_T,
                Ref('AWS::StackName'),
                Ref(ROOT_STACK_NAME)
            ),
            EnvironmentName=If(
                USE_STACK_NAME_CON_T,
                Ref('AWS::StackName'),
                Ref(ROOT_STACK_NAME)
            )
        )
    )
    igw = InternetGateway(
        IGW_T,
        template=template
    )
    VPCGatewayAttachment(
        "VPCGatewayAttachement",
        template=template,
        InternetGatewayId=Ref(igw),
        VpcId=Ref(vpc)
    )
    dhcp_opts = DHCPOptions(
        'VpcDhcpOptions',
        template=template,
        DomainName=If(
            USE_STACK_NAME_CON_T,
            Sub(f'${{AWS::StackName}}.${{{vpc_params.VPC_DNS_ZONE_T}}}'),
            Sub(f'${{{ROOT_STACK_NAME_T}}}.${{{vpc_params.VPC_DNS_ZONE_T}}}')
        ),
        DomainNameServers=['AmazonProvidedDNS'],
        Tags=Tags(
            Name=Sub(f'dhcp-${{{vpc.title}}}')
        )
    )
    VPCDHCPOptionsAssociation(
        'VpcDhcpOptionsAssociate',
        template=template,
        DhcpOptionsId=Ref(dhcp_opts),
        VpcId=Ref(vpc)
    )
    zone_con = template.add_condition(
        vpc_conditions.USE_SUB_ZONE_CON_T, vpc_conditions.USE_SUB_ZONE_CON
    )
    HostedZone(
        'VpcHostedZone',
        template=template,
        Condition=zone_con,
        VPCs=[
            HostedZoneVPCs(
                VPCId=Ref(vpc),
                VPCRegion=Ref('AWS::Region')
            )
        ],
        Name=If(
            USE_STACK_NAME_CON_T,
            Sub(f'sub.${{AWS::StackName}}.${{{vpc_params.VPC_DNS_ZONE_T}}}'),
            Sub(f'sub.${{{ROOT_STACK_NAME_T}}}.${{{vpc_params.VPC_DNS_ZONE_T}}}')
        ),
        HostedZoneTags=Tags(Name=Sub(f'ZoneFor-${{{vpc.title}}}'))
    )
    return (vpc, igw)


def generate_vpc_template(cidr_block, azs, session=None, single_nat=False):
    """
    Function to generate a new VPC template for CFN

    :param cidr_block: str of the CIDR used for this VPC
    :param azs: list of AWS Azs i.e. ['eu-west-1a', 'eu-west-1b']
    :param session: override session from boto3.session.Sesssion().
    :param single_nat: True/False if you want a single NAT for the Application Subnets
    :type single_nat: bool

    :return: Template() representing the VPC and associated resources
    """
    if session is None:
        session = boto3.session.Session()
    azs_count = len(azs)
    az_range = range(0, azs_count)
    layers = get_subnet_layers(cidr_block, len(azs))
    template = build_template(
        'VpcTemplate generated via ECS Compose X',
        [
            cfn_params.SERVICE_DISCOVERY,
            vpc_params.VPC_DNS_ZONE,
            vpc_params.USE_SUB_ZONE
        ]
    )
    template.add_mapping('AwsLbAccounts', aws_mappings.AWS_LB_ACCOUNTS)
    template.add_condition(
        USE_CLOUDMAP_CON_T,
        cfn_conditions.USE_CLOUDMAP_CON
    )
    template.add_condition(
        cfn_conditions.NOT_USE_CLOUDMAP_CON_T,
        cfn_conditions.NOT_USE_CLOUDMAP_CON
    )
    vpc = add_vpc_core(template, cidr_block)
    storage_subnets = add_storage_subnets(template, vpc[0], az_range, layers)
    public_subnets = add_public_subnets(template, vpc[0], az_range, layers, vpc[-1], single_nat)
    app_subnets = add_apps_subnets(template, vpc[0], az_range, layers, public_subnets[-1])
    add_template_outputs(
        template,
        vpc[0],
        storage_subnets[1],
        public_subnets[1],
        app_subnets[1],
    )
    add_vpc_cidrs_outputs(template, layers)
    add_cloudmap_support(template, vpc[0])
    validate_template(template.to_json(), 'vpc.json')
    with open('/tmp/vpc.json', 'w') as fd:
        fd.write(template.to_json())
    return template
