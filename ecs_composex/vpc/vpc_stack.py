﻿#  -*- coding: utf-8 -*-
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

import re
from troposphere import Ref, If
from troposphere import Parameter

from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.common import add_parameters, LOG, build_template
from ecs_composex.common import keyisset
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.vpc.vpc_template import (
    get_subnet_layers,
    aws_mappings,
    add_vpc_core,
    add_apps_subnets,
    add_public_subnets,
    add_storage_subnets,
    add_vpc_flow,
    add_template_outputs,
    add_vpc_cidrs_outputs,
)
from ecs_composex.vpc.vpc_params import (
    RES_KEY,
    VPC_ID,
    APP_SUBNETS,
    STORAGE_SUBNETS,
    PUBLIC_SUBNETS,
    DEFAULT_VPC_CIDR,
    VPC_CIDR,
    VPC_SINGLE_NAT,
    SUBNETS_TYPE,
)
from ecs_composex.dns import dns_params, dns_conditions
from ecs_composex.vpc.vpc_aws import lookup_x_vpc_settings

AZ_INDEX_PATTERN = r"(([a-z0-9-]+)([a-z]{1}$))"
AZ_INDEX_RE = re.compile(AZ_INDEX_PATTERN)


class VpcStack(ComposeXStack):
    """
    Class to create the VPC Stack
    """

    def __init__(self, title, settings, vpc_settings, **kwargs):

        if not keyisset("Endpoints", vpc_settings):
            endpoints = []
        else:
            endpoints = vpc_settings["Endpoints"]

        if endpoints is None:
            endpoints = []
        curated_azs = []
        for az in settings.aws_azs:
            if isinstance(az, dict):
                curated_azs.append(az["ZoneName"])
            elif isinstance(az, str):
                curated_azs.append(az)
        azs_index = [AZ_INDEX_RE.match(az).groups()[-1] for az in curated_azs]
        layers = get_subnet_layers(vpc_settings[VPC_CIDR.title], len(curated_azs))
        template = build_template(
            "VpcTemplate generated via ECS ComposeX",
            [dns_params.PRIVATE_DNS_ZONE_NAME],
        )
        LOG.debug(azs_index)
        template.add_mapping("AwsLbAccounts", aws_mappings.AWS_LB_ACCOUNTS)
        vpc_core = add_vpc_core(template, vpc_settings[VPC_CIDR.title])
        self.vpc = vpc_core[0]
        storage_subnets = add_storage_subnets(template, self.vpc, azs_index, layers)
        public_subnets = add_public_subnets(
            template,
            self.vpc,
            azs_index,
            layers,
            vpc_core[-1],
            vpc_settings[VPC_SINGLE_NAT.title],
        )
        app_subnets = add_apps_subnets(
            template, self.vpc, azs_index, layers, public_subnets[-1], endpoints
        )
        add_template_outputs(
            template,
            self.vpc,
            storage_subnets[1],
            public_subnets[1],
            app_subnets[1],
        )
        if keyisset("EnableFlowLogs", vpc_settings):
            print("ADDING FLOW LOGS")
            add_vpc_flow(
                template,
                self.vpc,
                boundary=vpc_settings["FlowLogsRoleBoundary"]
                if keyisset("FlowLogsRoleBoundary", vpc_settings)
                else None,
            )
        add_vpc_cidrs_outputs(template, self.vpc, layers)
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
    create_def.update(create_settings)
    return create_def


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


def set_subnets_from_use(subnets_list, vpc_settings, subnets_def):
    for subnet_name in subnets_list:
        if not isinstance(vpc_settings[subnet_name], (list, str)):
            raise TypeError(
                "The subnet_name must be of type", str, list, "Got", type(subnet_name)
            )
        subnets = (
            vpc_settings[subnet_name].split(",")
            if isinstance(vpc_settings[subnet_name], str)
            else vpc_settings[subnet_name]
        )
        subnets_def[subnet_name] = subnets


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
    extra_subnets = [key for key in vpc_settings.keys() if key not in required_subnets]
    set_subnets_from_use(required_subnets, vpc_settings, settings)
    set_subnets_from_use(extra_subnets, vpc_settings, settings)

    return settings


def apply_vpc_settings(x_settings, root_stack, settings):
    """

    :param x_settings:
    :param root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
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
    settings.subnets_parameters.append(APP_SUBNETS)
    settings.subnets_parameters.append(PUBLIC_SUBNETS)
    settings.subnets_parameters.append(STORAGE_SUBNETS)
    for setting_name in x_settings:
        if setting_name not in settings_params.keys():
            param = root_stack.stack_template.add_parameter(
                Parameter(setting_name, Type=SUBNETS_TYPE)
            )
            settings_params[param.title] = x_settings[param.title]
            settings.subnets_parameters.append(param)

    root_stack.Parameters.update(settings_params)
    settings.set_azs_from_vpc_import(
        public_subnets=x_settings[PUBLIC_SUBNETS.title],
        app_subnets=x_settings[APP_SUBNETS.title],
        storage_subnets=x_settings[STORAGE_SUBNETS.title],
    )


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
            settings.create_vpc = False
            x_settings = lookup_x_vpc_settings(
                settings.compose_content[vpc_xkey]["Lookup"], settings.session
            )
            apply_vpc_settings(x_settings, root_stack, settings)
        elif keyisset("Use", settings.compose_content[vpc_xkey]):
            x_settings = import_vpc_settings(settings.compose_content[vpc_xkey]["Use"])
            apply_vpc_settings(x_settings, root_stack, settings)
        else:
            if keyisset("Create", settings.compose_content[vpc_xkey]) and keyisset(
                "Lookup", settings.compose_content[vpc_xkey]
            ):
                settings.create_vpc = True
                LOG.warning(
                    "We have both Create and Lookup set for x-vpc." "Creating a new VPC"
                )
            vpc_stack = create_new_vpc(vpc_xkey, settings)
            settings.create_vpc = True
    else:
        LOG.info(f"No {vpc_xkey} detected. Creating a new VPC.")
        vpc_stack = create_new_vpc(vpc_xkey, settings, default=True)
        settings.create_vpc = True
    if isinstance(vpc_stack, VpcStack):
        root_stack.stack_template.add_resource(vpc_stack)
    return vpc_stack
