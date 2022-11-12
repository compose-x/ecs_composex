# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for VpcStack
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

import re

import troposphere
from botocore.exceptions import ClientError
from compose_x_common.aws import get_region_azs
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import FindInMap, GetAtt, Join, Ref
from troposphere.servicediscovery import PrivateDnsNamespace

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resources_import import (
    find_aws_properties_in_aws_resource,
    find_aws_resources_in_template_resources,
)
from ecs_composex.vpc import aws_mappings
from ecs_composex.vpc.vpc_aws import lookup_x_vpc_settings
from ecs_composex.vpc.vpc_maths import get_subnet_layers
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS,
    APP_SUBNETS_CIDR,
    DEFAULT_VPC_CIDR,
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

from ..common.troposphere_tools import add_outputs, build_template
from ..compose.x_resources.environment_x_resources import AwsEnvironmentResource
from .vpc_cloudmap import x_vpc_to_x_cloudmap

AZ_INDEX_PATTERN = r"(([a-z0-9-]+)([a-z]{1}$))"
AZ_INDEX_RE = re.compile(AZ_INDEX_PATTERN)


class Vpc(AwsEnvironmentResource):
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
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        self.vpc = None
        self.vpc_cidr = None
        self.app_subnets = []
        self.public_subnets = []
        self.storage_subnets = []
        self.subnets = []
        self.subnets_parameters = []
        self.endpoints = []
        self.endpoints_sg = None
        self.logging = None
        self.layers = None
        self.azs = {}
        super().__init__(name, definition, module, settings)

    def storage_subnets_count(self) -> int:
        if self.cfn_resource and self.storage_subnets:
            return len(self.storage_subnets[-1])
        elif self.mappings:
            return len(self.mappings[STORAGE_SUBNETS.title]["Ids"])
        else:
            raise AttributeError(
                f"VPC is not set. Cannot determine the count for {STORAGE_SUBNETS.title}"
            )

    def create_vpc(self, template, settings):
        """
        Creates a new VPC from Properties (or from defaults)

        :param troposhere.Template template:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.endpoints = set_else_none("Endpoints", self.properties, [])
        self.vpc_cidr = set_else_none(
            VPC_CIDR.title, self.properties, self.default_ipv4_cidr
        )
        curated_azs = []
        current_region_azs = [
            zone["ZoneName"]
            for zone in settings.session.client("ec2").describe_availability_zones()[
                "AvailabilityZones"
            ][:2]
        ]
        for az in current_region_azs:
            if isinstance(az, dict):
                curated_azs.append(az["ZoneName"])
            elif isinstance(az, str):
                curated_azs.append(az)
        azs_index = [AZ_INDEX_RE.match(az).groups()[-1] for az in curated_azs]
        self.azs[PUBLIC_SUBNETS] = current_region_azs
        self.azs[STORAGE_SUBNETS] = current_region_azs
        self.azs[APP_SUBNETS] = current_region_azs

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
                VPC_SINGLE_NAT.title,
                self.properties,
                bool(VPC_SINGLE_NAT.Default),
            ),
            set_else_none("DisableNat", self.properties, False),
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
        self.cfn_resource = self.vpc
        self.subnets_parameters.append(APP_SUBNETS)
        self.subnets_parameters.append(PUBLIC_SUBNETS)
        self.subnets_parameters.append(STORAGE_SUBNETS)

    def lookup_vpc(self, settings):
        """
        Method to set VPC settings from x-vpc

        :return: vpc_settings
        :rtype: dict
        """
        vpc_settings = lookup_x_vpc_settings(self)
        self.create_vpc_mappings(vpc_settings)
        LOG.info(f"{RES_KEY} - Found VPC - {self.mappings[VPC_ID.title][VPC_ID.title]}")

    def create_vpc_mappings(self, vpc_settings):
        """
        Generates the VPC CFN Mappings

        :param vpc_settings:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        self.mappings = {
            VPC_ID.title: {VPC_ID.title: vpc_settings[VPC_ID.title]},
            APP_SUBNETS.title: {"Ids": vpc_settings[APP_SUBNETS.title]},
            STORAGE_SUBNETS.title: {"Ids": vpc_settings[STORAGE_SUBNETS.title]},
            PUBLIC_SUBNETS.title: {"Ids": vpc_settings[PUBLIC_SUBNETS.title]},
        }
        ignored_keys = ["RoleArn", "session"]
        self.subnets_parameters.append(APP_SUBNETS)
        self.subnets_parameters.append(PUBLIC_SUBNETS)
        self.subnets_parameters.append(STORAGE_SUBNETS)
        for setting_name in vpc_settings:
            if (
                setting_name not in self.mappings.keys()
                and setting_name not in ignored_keys
            ):
                self.mappings[setting_name] = {"Ids": vpc_settings[setting_name]}
                param = Parameter(setting_name, Type=SUBNETS_TYPE)
                self.subnets_parameters.append(param)

        self.set_azs_from_vpc_import(
            vpc_settings,
            session=vpc_settings["session"]
            if keyisset("session", vpc_settings)
            else None,
        )

    def set_azs_from_api(self):
        """
        Method to set the AWS Azs based on DescribeAvailabilityZones
        :return:
        """
        try:
            self.aws_azs = get_region_azs(self.lookup_session)
        except ClientError as error:
            code = error.response["Error"]["Code"]
            message = error.response["Error"]["Message"]
            if code == "RequestExpired":
                LOG.error(message)
                LOG.warning(f"Due to error, using default values {self.aws_azs}")

            else:
                LOG.error(error)

    def set_azs_from_vpc_import(self, subnets, session=None):
        """
        Function to get the list of AZs for a given set of subnets

        :param dict subnets:
        :param session: The Session used to find the EC2 subnets (useful for lookup).
        :return:
        """
        if session is None:
            client = self.lookup_session.client("ec2")
        else:
            client = session.client("ec2")
        for subnet_name, subnet_definition in subnets.items():
            if not isinstance(subnet_definition, list):
                continue
            for subnet_param in self.subnets_parameters:
                if subnet_param.title == subnet_name:
                    subnets_param = subnet_param
                    break
            else:
                raise KeyError(
                    f"x-vpc.set_azs_from_vpc_import - No parameter defined for {subnet_name}"
                )
            try:
                subnets_r = client.describe_subnets(SubnetIds=subnet_definition)[
                    "Subnets"
                ]
                azs = [subnet["AvailabilityZone"] for subnet in subnets_r]
                self.mappings[subnet_name]["Azs"] = azs
                self.azs[subnets_param] = azs
            except ClientError:
                LOG.warning("Could not define the AZs based on the imported subnets")

    def init_outputs(self):
        """
        Initialize output properties to pass on to the other stacks that need these values
        """
        self.output_properties = {
            VPC_ID: (VPC_ID.title, self.vpc, Ref, None),
            APP_SUBNETS: (
                APP_SUBNETS.title,
                self.app_subnets[1],
                Join,
                [",", [Ref(subnet) for subnet in self.app_subnets[1]]],
            ),
            PUBLIC_SUBNETS: (
                PUBLIC_SUBNETS.title,
                self.public_subnets[1],
                Join,
                [",", [Ref(subnet) for subnet in self.public_subnets[1]]],
            ),
            STORAGE_SUBNETS: (
                STORAGE_SUBNETS.title,
                self.storage_subnets[1],
                Join,
                [",", [Ref(subnet) for subnet in self.storage_subnets[1]]],
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

    def handle_x_dependencies(self, settings, root_stack):
        """
        Function to have x-vpc update resources that have the x-vpc value where VpcID should be.

        :param ecs_composex.common.settings.ComposeXSettings settings: the execution settings
        :param ecs_composex.common.stacks.ComposeXStack root_stack: unused today
        """
        for resource in settings.get_x_resources(include_mappings=False):
            if not resource.cfn_resource:
                continue
            resource_stack = resource.stack
            if not resource_stack:
                LOG.debug(
                    f"resource {resource.name} has no `stack` attribute defined. Skipping"
                )
                continue
            x_to_x_mappings = [
                (
                    x_vpc_to_x_cloudmap,
                    (PrivateDnsNamespace,),
                    str,
                    "Vpc",
                )
            ]
            for update_settings in x_to_x_mappings:
                aws_resources_to_update = find_aws_resources_in_template_resources(
                    resource_stack, update_settings[1]
                )
                for stack_resource in aws_resources_to_update:
                    properties_to_update = find_aws_properties_in_aws_resource(
                        update_settings[2], stack_resource
                    )
                    update_settings[0](
                        self,
                        stack_resource,
                        resource_stack,
                        properties_to_update,
                        update_settings[3],
                        settings,
                    )


def init_vpc_template() -> troposphere.Template:
    """
    Simple wrapper function to create the VPC Template

    :rtype: troposhere.Template
    """
    template = build_template(
        "Vpc Template generated via ECS Compose-X",
    )
    template.add_mapping("AwsLbAccounts", aws_mappings.AWS_LB_ACCOUNTS)
    return template


class XStack(ComposeXStack):
    """
    Class to create the VPC Stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        self.is_void = True
        self.vpc_resource = None
        if not keyisset(module.res_key, settings.compose_content):
            LOG.warning(f"{module.res_key} - not defined. Assuming no VPC")
            self.is_void = True
        else:
            self.vpc_resource = Vpc(
                "vpc", settings.compose_content[module.res_key], module, settings
            )
            if self.vpc_resource.lookup:
                self.vpc_resource.lookup_vpc(settings)
            elif self.vpc_resource.properties:
                template = init_vpc_template()
                self.vpc_resource.create_vpc(template, settings)
                self.is_void = False
                self.vpc_resource.init_outputs()
                super().__init__(title, stack_template=template, **kwargs)
                self.vpc_resource.generate_outputs()
                add_outputs(template, self.vpc_resource.outputs)
            self.vpc_resource.stack = self

    def create_new_default_vpc(self, title, vpc_module, settings):
        """
        In case no x-vpc was specified but the deployment settings require a new VPC, allows for an easy way to set one.
        """
        self.vpc_resource = Vpc(
            name="vpc",
            definition={"Properties": {VPC_CIDR.title: Vpc.default_ipv4_cidr}},
            module=vpc_module,
            settings=settings,
        )
        template = init_vpc_template()
        self.vpc_resource.create_vpc(template, settings)
        self.is_void = False
        self.vpc_resource.init_outputs()
        super().__init__(title, stack_template=template)
        self.vpc_resource.generate_outputs()
        add_outputs(template, self.vpc_resource.outputs)
        self.vpc_resource.stack = self

    @property
    def vpc_id(self):
        """
        Gives the VPC ID
        :return:
        """
        if not self.is_void and self.vpc_resource:
            return GetAtt(self.title, f"Outputs.{VPC_ID.title}")
        elif self.is_void and self.vpc_resource.mappings:
            return FindInMap("Network", VPC_ID.title, VPC_ID.title)
        else:
            return None
