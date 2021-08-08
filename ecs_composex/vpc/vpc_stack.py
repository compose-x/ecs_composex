#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for VpcStack
"""

import re

from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap

from ecs_composex.common import LOG, build_template
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dns import dns_params
from ecs_composex.vpc import aws_mappings
from ecs_composex.vpc.vpc_aws import lookup_x_vpc_settings
from ecs_composex.vpc.vpc_maths import get_subnet_layers
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS,
    DEFAULT_VPC_CIDR,
    PUBLIC_SUBNETS,
    RES_KEY,
    STORAGE_SUBNETS,
    SUBNETS_TYPE,
    VPC_CIDR,
    VPC_ID,
    VPC_SINGLE_NAT,
)
from ecs_composex.vpc.vpc_subnets import (
    add_apps_subnets,
    add_public_subnets,
    add_storage_subnets,
)
from ecs_composex.vpc.vpc_template import (
    add_template_outputs,
    add_vpc_cidrs_outputs,
    add_vpc_core,
    add_vpc_flow,
)

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
            dns_params.PRIVATE_DNS_ZONE_NAME.title: FindInMap(
                "Dns",
                "PrivateNamespace",
                dns_params.PRIVATE_DNS_ZONE_NAME.title,
            )
        }
    )
    return vpc_stack


def set_subnets_from_use(subnets_list, vpc_settings, subnets_def):
    for subnet_name in subnets_list:
        if not isinstance(vpc_settings[subnet_name], (list, str)):
            raise TypeError(
                "The subnet_name must be of type",
                str,
                list,
                "Got",
                type(subnet_name),
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
    required_subnets = [
        APP_SUBNETS.title,
        PUBLIC_SUBNETS.title,
        STORAGE_SUBNETS.title,
    ]
    excluded = [VPC_ID.title, "RoleArn"]
    if not all(subnet in vpc_settings.keys() for subnet in required_subnets):
        raise KeyError("All required subnets must be indicated", required_subnets)
    extra_subnets = [
        key
        for key in vpc_settings.keys()
        if key not in required_subnets and key not in excluded
    ]
    set_subnets_from_use(required_subnets, vpc_settings, settings)
    set_subnets_from_use(extra_subnets, vpc_settings, settings)

    return settings


def create_vpc_mapping(settings_params):
    """
    Function to create a CFN Mapping to use and assign subnets to substacks

    :param settings_params:
    :return:
    """


def apply_vpc_settings(x_settings, root_stack, settings):
    """

    :param x_settings:
    :param root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    settings.subnets_mappings = {
        VPC_ID.title: {VPC_ID.title: x_settings[VPC_ID.title]},
        APP_SUBNETS.title: {"Ids": x_settings[APP_SUBNETS.title]},
        STORAGE_SUBNETS.title: {"Ids": x_settings[STORAGE_SUBNETS.title]},
        PUBLIC_SUBNETS.title: {"Ids": x_settings[PUBLIC_SUBNETS.title]},
    }
    ignored_keys = ["RoleArn", "session"]
    settings.subnets_parameters.append(APP_SUBNETS)
    settings.subnets_parameters.append(PUBLIC_SUBNETS)
    settings.subnets_parameters.append(STORAGE_SUBNETS)
    for setting_name in x_settings:
        if (
            setting_name not in settings.subnets_mappings.keys()
            and setting_name not in ignored_keys
        ):
            settings.subnets_mappings[setting_name] = {"Ids": x_settings[setting_name]}
            param = Parameter(setting_name, Type=SUBNETS_TYPE)
            settings.subnets_parameters.append(param)

    root_stack.stack_template.add_mapping("Network", settings.subnets_mappings)
    settings.set_azs_from_vpc_import(
        x_settings,
        session=x_settings["session"] if keyisset("session", x_settings) else None,
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
                    "We have both Create and Lookup set for x-vpc. Creating a new VPC"
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
