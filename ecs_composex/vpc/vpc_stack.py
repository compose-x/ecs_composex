#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for VpcStack
"""

import re
from copy import deepcopy

import troposphere
from compose_x_common.compose_x_common import keyisset
from troposphere import Join, Ref

from ecs_composex.common import LOG, build_template, set_else_none
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import XResource
from ecs_composex.dns import dns_params
from ecs_composex.vpc import aws_mappings
from ecs_composex.vpc.vpc_aws import lookup_x_vpc_settings
from ecs_composex.vpc.vpc_maths import get_subnet_layers
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS,
    APP_SUBNETS_CIDR,
    DEFAULT_VPC_CIDR,
    MOD_KEY,
    PUBLIC_SUBNETS,
    PUBLIC_SUBNETS_CIDR,
    RES_KEY,
    STORAGE_SUBNETS,
    STORAGE_SUBNETS_CIDR,
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
from ecs_composex.vpc.vpc_template import add_vpc_core, add_vpc_flow

AZ_INDEX_PATTERN = r"(([a-z0-9-]+)([a-z]{1}$))"
AZ_INDEX_RE = re.compile(AZ_INDEX_PATTERN)


def set_subnets_from_use(subnets_list, vpc_settings, subnets_def):
    """
    Sets the subnets IDs from x-vpc.Use
    """
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


class Vpc(XResource):
    """
    Class to represent the VPC
    """

    default_ipv4_cidr = DEFAULT_VPC_CIDR
    required_subnets = [
        APP_SUBNETS.title,
        PUBLIC_SUBNETS.title,
        STORAGE_SUBNETS.title,
    ]

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        self.vpc = None
        self.vpc_cidr = None
        self.app_subnets = []
        self.public_subnets = []
        self.storage_subnets = []
        self.subnets = []
        self.endpoints = []
        self.endpoints_sg = None
        self.logging = None
        self.layers = None
        super().__init__(name, definition, module_name, settings, mapping_key)

    def create_vpc(self, template, settings, default=False):
        """
        Creates a new VPC from Properties (or from defaults)
        """
        self.endpoints = set_else_none("Endpoints", self.properties, [])
        self.vpc_cidr = set_else_none(
            VPC_CIDR.title, self.properties, self.default_ipv4_cidr
        )
        curated_azs = []
        for az in settings.aws_azs:
            if isinstance(az, dict):
                curated_azs.append(az["ZoneName"])
            elif isinstance(az, str):
                curated_azs.append(az)
        azs_index = [AZ_INDEX_RE.match(az).groups()[-1] for az in curated_azs]

        self.layers = get_subnet_layers(self.vpc_cidr, len(curated_azs))
        vpc_core = add_vpc_core(template, self.vpc_cidr)
        self.vpc = vpc_core[0]
        self.storage_subnets = add_storage_subnets(
            template, self.vpc, azs_index, self.layers
        )
        self.public_subnets = add_public_subnets(
            template,
            self.vpc,
            azs_index,
            self.layers,
            vpc_core[-1],
            set_else_none(
                VPC_SINGLE_NAT.title, self.properties, bool(VPC_SINGLE_NAT.Default)
            ),
        )
        self.app_subnets = add_apps_subnets(
            template,
            self.vpc,
            azs_index,
            self.layers,
            self.public_subnets[-1],
            self.endpoints,
        )
        if keyisset("EnableFlowLogs", self.properties):
            add_vpc_flow(
                template,
                self.vpc,
                boundary=set_else_none("FlowLogsRoleBoundary", self.properties, None),
            )

    def lookup_vpc(self, settings):
        """
        Method to set VPC settings from x-vpc

        :return: vpc_settings
        :rtype: dict
        """
        vpc_settings = lookup_x_vpc_settings(self)
        self.create_vpc_mappings(vpc_settings, settings)
        LOG.info(f"{RES_KEY} - Found VPC - {self.mappings[VPC_ID.title][VPC_ID.title]}")

    def use_vpc(self, settings):
        """
        Function to import settings set "in-stone" from docker-compose definition

        :return: settings
        :rtype dict:
        """
        if not keyisset(VPC_ID.title, self.use):
            raise KeyError("You must specify the VPC ID to use for deployment")
        vpc_settings = {VPC_ID.title: self.use[VPC_ID.title]}

        excluded = [VPC_ID.title, "RoleArn"]
        if not all(subnet in self.use.keys() for subnet in self.required_subnets):
            raise KeyError(
                "All required subnets must be indicated", self.required_subnets
            )
        extra_subnets = [
            key
            for key in self.use.keys()
            if key not in self.required_subnets and key not in excluded
        ]
        set_subnets_from_use(self.required_subnets, self.use, vpc_settings)
        set_subnets_from_use(extra_subnets, self.use, vpc_settings)

        self.create_vpc_mappings(vpc_settings, settings)

    def create_vpc_mappings(self, vpc_settings, settings):
        """
        Generates the VPC CFN Mappings

        :param vpc_settings:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        settings.subnets_mappings = {
            VPC_ID.title: {VPC_ID.title: vpc_settings[VPC_ID.title]},
            APP_SUBNETS.title: {"Ids": vpc_settings[APP_SUBNETS.title]},
            STORAGE_SUBNETS.title: {"Ids": vpc_settings[STORAGE_SUBNETS.title]},
            PUBLIC_SUBNETS.title: {"Ids": vpc_settings[PUBLIC_SUBNETS.title]},
        }
        ignored_keys = ["RoleArn", "session"]
        settings.subnets_parameters.append(APP_SUBNETS)
        settings.subnets_parameters.append(PUBLIC_SUBNETS)
        settings.subnets_parameters.append(STORAGE_SUBNETS)
        for setting_name in vpc_settings:
            if (
                setting_name not in settings.subnets_mappings.keys()
                and setting_name not in ignored_keys
            ):
                settings.subnets_mappings[setting_name] = {
                    "Ids": vpc_settings[setting_name]
                }
                param = Parameter(setting_name, Type=SUBNETS_TYPE)
                settings.subnets_parameters.append(param)

        settings.set_azs_from_vpc_import(
            vpc_settings,
            session=vpc_settings["session"]
            if keyisset("session", vpc_settings)
            else None,
        )
        self.mappings = deepcopy(settings.subnets_mappings)

    def init_outputs(self):
        """
        Initialize output properties to pass on to the other stacks that need these values
        """
        self.output_properties = {
            VPC_ID: (VPC_ID.title, self.vpc, Ref, None),
            APP_SUBNETS: (
                APP_SUBNETS.title,
                self.app_subnets,
                Join,
                [",", [Ref(subnet) for subnet in self.app_subnets]],
            ),
            PUBLIC_SUBNETS: (
                PUBLIC_SUBNETS.title,
                self.public_subnets,
                Join,
                [",", [Ref(subnet) for subnet in self.public_subnets]],
            ),
            STORAGE_SUBNETS: (
                STORAGE_SUBNETS.title,
                self.storage_subnets,
                Join,
                [",", [Ref(subnet) for subnet in self.storage_subnets]],
            ),
            STORAGE_SUBNETS_CIDR: (
                STORAGE_SUBNETS_CIDR.title,
                None,
                Join,
                [",", [cidr for cidr in self.layers["stor"]]],
            ),
            APP_SUBNETS_CIDR: (
                APP_SUBNETS_CIDR.title,
                None,
                Join,
                [",", [cidr for cidr in self.layers["app"]]],
            ),
            PUBLIC_SUBNETS_CIDR: (
                PUBLIC_SUBNETS_CIDR.title,
                None,
                Join,
                [",", [cidr for cidr in self.layers["pub"]]],
            ),
        }


def init_vpc_template() -> troposphere.Template:
    """
    Simple wrapper function to create the VPC Template

    :rtype: troposhere.Template
    """
    template = build_template(
        "Vpc Template generated via ECS Compose-X",
        [dns_params.PRIVATE_DNS_ZONE_NAME],
    )
    template.add_mapping("AwsLbAccounts", aws_mappings.AWS_LB_ACCOUNTS)
    return template


class VpcStack(ComposeXStack):
    """
    Class to create the VPC Stack
    """

    def __init__(self, title, settings, **kwargs):
        self.is_void = True
        self.vpc_resource = None
        if not keyisset(RES_KEY, settings.compose_content):
            LOG.warning(f"{RES_KEY} - not defined. Assuming no VPC")
            self.is_void = True
        else:
            self.vpc_resource = Vpc(
                "vpc", settings.compose_content[RES_KEY], "vpc", settings, "vpc"
            )
            if self.vpc_resource.lookup:
                self.vpc_resource.lookup_vpc(settings)
            elif self.vpc_resource.use:
                self.vpc_resource.use_vpc(settings)
            elif self.vpc_resource.properties:
                template = init_vpc_template()
                self.vpc_resource.create_vpc(template, settings)
                self.is_void = False
                self.vpc_resource.init_outputs()
                super().__init__(title, stack_template=template, **kwargs)

    def create_new_vpc(self, title, settings):
        """
        In case no x-vpc was specified but the deployment settings require a new VPC, allows for an easy way to set one.
        """
        self.vpc_resource = Vpc(
            "vpc",
            {"Properties": {VPC_CIDR.title: Vpc.default_ipv4_cidr}},
            "vpc",
            settings,
            "vpc",
        )
        template = init_vpc_template()
        self.vpc_resource.create_vpc(template, settings)
        self.is_void = False
        self.vpc_resource.init_outputs()
        super().__init__(title, stack_template=template)
