#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module for VpcStack
"""

from troposphere import Ref, If

from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.common import add_parameters, LOG
from ecs_composex.common import keyisset
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.vpc.vpc_template import generate_vpc_template
from ecs_composex.vpc.vpc_params import (
    RES_KEY,
    VPC_ID,
    APP_SUBNETS,
    STORAGE_SUBNETS,
    PUBLIC_SUBNETS,
    DEFAULT_VPC_CIDR,
    VPC_CIDR,
    VPC_SINGLE_NAT,
)
from ecs_composex.dns import dns_params, dns_conditions
from ecs_composex.vpc.vpc_aws import lookup_x_vpc_settings


class VpcStack(ComposeXStack):
    """
    Class to create the VPC Stack
    """

    def __init__(self, title, settings, vpc_settings, **kwargs):
        template = generate_vpc_template(
            cidr_block=vpc_settings[VPC_CIDR.title],
            azs=settings.aws_azs,
            single_nat=vpc_settings[VPC_SINGLE_NAT.title],
            endpoints=vpc_settings["Endpoints"]
            if keyisset("Endpoints", vpc_settings)
            else None,
        )
        super().__init__(title, stack_template=template, **kwargs)


def define_create_settings(create_def):
    """
    Function to create the VPC creation settings

    :param dict create_def:
    :return:
    """
    create_settings = {
        VPC_CIDR.title: create_def[VPC_CIDR.title]
        if keyisset(VPC_CIDR.title, create_def)
        else DEFAULT_VPC_CIDR,
        VPC_SINGLE_NAT.title: True
        if not keyisset(VPC_SINGLE_NAT.title, create_def)
        else create_def[VPC_SINGLE_NAT.title],
        "Endpoints": create_def["Endpoints"]
        if keyisset("Endpoints", create_def)
        else [],
    }
    return create_settings


def create_new_vpc(vpc_xkey, settings, default=False):
    if not default:
        create_settings = define_create_settings(
            settings.compose_content[vpc_xkey]["Create"]
        )
    else:
        create_settings = {
            VPC_CIDR.title: DEFAULT_VPC_CIDR,
            VPC_SINGLE_NAT.title: True,
            "Endpoints": {
                "AwsServices": [{"service": "ecr.dkr"}, {"service": "ecr.api"}]
            },
        }
    vpc_stack = VpcStack(RES_KEY, settings, create_settings)
    vpc_stack.add_parameter(
        {
            dns_params.PRIVATE_DNS_ZONE_NAME.title: If(
                dns_conditions.USE_DEFAULT_ZONE_NAME_CON_T,
                dns_params.DEFAULT_PRIVATE_DNS_ZONE,
                Ref(dns_params.PRIVATE_DNS_ZONE_NAME),
            ),
        }
    )
    return vpc_stack


def import_vpc_settings(vpc_settings):
    """
    Function to import settings set "in-stone" from docker-compose definition

    :param dict vpc_settings:
    :return: settings
    :rtype dict:
    """
    if not keyisset(VPC_ID.title, vpc_settings):
        raise KeyError("You must specify the VPC ID to use for deployment")
    settings = {VPC_ID.title: vpc_settings[VPC_ID.title]}
    required_subnets = [APP_SUBNETS.title, PUBLIC_SUBNETS.title, STORAGE_SUBNETS.title]
    if not all(subnet in vpc_settings.keys() for subnet in required_subnets):
        raise KeyError("All subnets must be indicated", required_subnets)
    for subnet_name in required_subnets:
        if not isinstance(vpc_settings[subnet_name], (list, str)):
            raise TypeError(
                "The subnet_name must be of type", str, list, "Got", type(subnet_name)
            )
        subnets = (
            vpc_settings[subnet_name].split(",")
            if isinstance(vpc_settings[subnet_name], str)
            else vpc_settings[subnet_name]
        )
        settings[subnet_name] = subnets
    return settings


def apply_vpc_settings(x_settings, root_stack):
    """

    :param x_settings:
    :param root_stack:
    :return:
    """
    add_parameters(
        root_stack.stack_template,
        [VPC_ID, APP_SUBNETS, STORAGE_SUBNETS, PUBLIC_SUBNETS],
    )
    settings_params = {
        VPC_ID.title: x_settings[VPC_ID.title],
        APP_SUBNETS.title: x_settings[APP_SUBNETS.title],
        STORAGE_SUBNETS.title: x_settings[STORAGE_SUBNETS.title],
        PUBLIC_SUBNETS.title: x_settings[PUBLIC_SUBNETS.title],
    }
    root_stack.Parameters.update(settings_params)


def add_vpc_to_root(root_stack, settings):
    """
    Function to figure whether to create the VPC Stack and if not, set the parameters.

    :param root_stack:
    :param settings:
    :return: vpc_stack
    :rtype: VpcStack
    """
    vpc_stack = None
    vpc_xkey = f"{X_KEY}{RES_KEY}"

    if keyisset(vpc_xkey, settings.compose_content):
        if keyisset("Lookup", settings.compose_content[vpc_xkey]):
            x_settings = lookup_x_vpc_settings(
                settings.session, settings.compose_content[vpc_xkey]["Lookup"]
            )
            apply_vpc_settings(x_settings, root_stack)
        elif keyisset("Use", settings.compose_content[vpc_xkey]):
            x_settings = import_vpc_settings(settings.compose_content[vpc_xkey]["Use"])
            apply_vpc_settings(x_settings, root_stack)
        else:
            if keyisset("Create", settings.compose_content[vpc_xkey]) and keyisset(
                "Lookup", settings.compose_content[vpc_xkey]
            ):
                LOG.warning(
                    "We have both Create and Lookup set for x-vpc." "Creating a new VPC"
                )
            vpc_stack = create_new_vpc(vpc_xkey, settings)
    else:
        LOG.info(f"No {vpc_xkey} detected. Creating a new VPC.")
        vpc_stack = create_new_vpc(vpc_xkey, settings, default=True)
    if isinstance(vpc_stack, VpcStack):
        root_stack.stack_template.add_resource(vpc_stack)
    return vpc_stack
