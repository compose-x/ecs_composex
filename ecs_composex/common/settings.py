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
Module for the ComposeXSettings class
"""

from datetime import datetime as dt
from json import dumps


import boto3
from botocore.exceptions import ClientError

from ecs_composex import __version__
from ecs_composex.common import keyisset, LOG, load_composex_file
from ecs_composex.common.aws import get_account_id, get_region_azs
from ecs_composex.common.aws import (
    lookup_vpc_id,
    lookup_vpc_from_tags,
    lookup_subnets_from_tags,
    lookup_subnets_ids,
)
from ecs_composex.common.cfn_params import USE_FLEET_T
from ecs_composex.vpc.vpc_params import (
    VPC_ID_T,
    PUBLIC_SUBNETS_T,
    APP_SUBNETS_T,
    STORAGE_SUBNETS_T,
)


class ComposeXSettings(object):
    """
    Class to handle the settings to use for ECS ComposeX.
    """

    name_arg = "Name"
    cluster_name_arg = "ClusterName"

    create_vpc_arg = "CreateVpc"
    create_ec2_arg = "AddComputeResources"
    create_spotfleet_arg = USE_FLEET_T

    region_arg = "RegionName"
    zones_arg = "Zones"

    deploy_arg = "up"
    no_upload_arg = "config"
    command_arg = "command"

    bucket_arg = "BucketName"
    input_file_arg = "DockerComposeXFile"
    output_dir_arg = "OutputDirectory"
    format_arg = "TemplateFormat"
    default_format = "json"
    allowed_formats = ["json", "yaml", "text"]

    vpc_cidr_arg = "VpcCidr"
    single_nat_arg = "SingleNat"

    default_vpc_cidr = "100.127.254.0/24"
    default_azs = ["eu-west-1a", "eu-west-1b"]
    default_output_dir = f"/tmp/{dt.utcnow().strftime('%s')}"

    commands = ["up", "config", "version"]

    def __init__(self, content=None, profile_name=None, session=None, **kwargs):
        """
        Class to init the configuration
        """
        self.session = boto3.session.Session()
        self.override_session(session, profile_name)
        self.aws_region = (
            kwargs[self.region_arg]
            if keyisset(self.region_arg, kwargs)
            else self.session.region_name
        )
        self.aws_azs = self.default_azs
        if content is None:
            self.compose_content = load_composex_file(kwargs[self.input_file_arg])
        elif content and isinstance(content, dict):
            self.compose_content = content
        self.input_file = (
            kwargs[self.input_file_arg] if keyisset(self.input_file_arg, kwargs) else {}
        )
        self.account_id = None

        self.bucket_name = None
        self.output_dir = self.default_output_dir
        self.format = self.default_format
        self.set_output_settings(kwargs)

        self.no_upload = True if keyisset(self.no_upload_arg, kwargs) else False
        self.upload = False if self.no_upload else True
        self.name = kwargs[self.name_arg]
        self.create_compute = False if not keyisset(USE_FLEET_T, kwargs) else True

        self.vpc_private_namespace_id = None
        self.vpc_private_namespace_zone_id = None
        self.vpc_private_namespace_tld = None

        self.create_vpc = False
        self.vpc_cidr = None
        self.single_nat = None
        self.lookup_vpc = False
        self.set_vpc(kwargs)

        self.deploy = True if keyisset(self.deploy_arg, kwargs) else False
        self.parse_command(kwargs)

    def __repr__(self):
        return dumps(
            {
                self.region_arg: self.aws_region,
                self.zones_arg: self.aws_azs,
                self.bucket_arg: self.bucket_name,
                self.no_upload_arg: self.no_upload,
                self.deploy_arg: self.deploy,
            },
            indent=4,
        )

    def parse_command(self, kwargs):
        """
        Method to analyze the command and set execution settings accordingly.

        :param kwargs:
        :return:
        """
        command = kwargs[self.command_arg]
        if command not in self.commands:
            raise ValueError(f"{command} unknown. Valid commands are", self.commands)
        if command == self.bucket_arg:
            self.deploy = True
            self.upload = True
        elif command == self.no_upload_arg:
            self.no_upload = True
            self.upload = not self.no_upload
        elif command == "version":
            print("ECS ComposeX", __version__)
            exit(0)

    def set_vpc(self, kwargs):
        """
        Method to set the VPC settings.

        :param kwargs: the execution arguments
        """
        if keyisset("x-vpc", self.compose_content):
            if keyisset("Create", self.compose_content["x-vpc"]) and keyisset(
                "Lookup", self.compose_content["x-vpc"]
            ):
                LOG.warning(
                    "We have both Create and Lookup set for x-vpc. Applying default behaviour."
                )
                self.set_vpc_default_settings()
            elif keyisset("Lookup", self.compose_content["x-vpc"]):
                self.create_vpc = False
                self.lookup_x_vpc_settings(self.compose_content["x-vpc"]["Lookup"])
            elif keyisset("Create", self.compose_content["x-vpc"]):
                self.create_vpc = True
                self.set_x_vpc_settings(self.compose_content["x-vpc"]["Create"])

            else:
                LOG.error(
                    "x-vpc indicated but neither Create or Update is indicated. Going with default behaviour"
                )
                self.set_vpc_default_settings()
        elif not keyisset("x-vpc", self.compose_content):
            LOG.warning(
                "No x-vpc definition found in the docker-compose file. Creating a new VPC with default settings"
            )
            self.set_vpc_defaults(kwargs)

    def override_session(self, session, profile_name):
        """
        Method to set the session based on input params

        :param boto3.session.Session session: The session to override the API calls with
        :param str profile_name: Name of a profile configured in .aws/config
        """
        if profile_name and not session:
            self.session = boto3.session.Session(profile_name=profile_name)
        elif session and not profile_name:
            self.session = session

    def set_output_settings(self, kwargs):
        """
        Method to set the output settings based on kwargs
        """
        self.bucket_name = (
            kwargs[self.bucket_arg] if keyisset(self.bucket_arg, kwargs) else None
        )
        self.format = self.default_format
        if (
            keyisset(self.format_arg, kwargs)
            and kwargs[self.format_arg] in self.allowed_formats
        ):
            self.format = kwargs[self.format_arg]

        self.output_dir = (
            kwargs[self.output_dir_arg]
            if keyisset(self.output_dir_arg, kwargs)
            else self.default_output_dir
        )

    def lookup_vpc_id(self, vpc_id_settings):
        """
        Method to confirm or find VPC ID

        :param vpc_id_settings:
        """
        if isinstance(vpc_id_settings, str):
            setattr(self, VPC_ID_T, lookup_vpc_id(self.session, vpc_id_settings))
        elif (
            isinstance(vpc_id_settings, dict)
            and keyisset("tags", vpc_id_settings)
            and isinstance(vpc_id_settings["tags"], list)
        ):
            setattr(
                self,
                VPC_ID_T,
                lookup_vpc_from_tags(self.session, vpc_id_settings["tags"]),
            )
        else:
            raise ValueError(
                "VpcId is neither the VPC ID, the VPC Arn or a set of tags"
            )

    def lookup_subnets_ids(self, subnet_key, subnet_id_settings):
        """
        Method to confirm or find VPC ID

        :param str subnet_key: Attribute name
        :param subnet_id_settings:
        """
        if isinstance(subnet_id_settings, str):
            setattr(
                self,
                subnet_key,
                lookup_subnets_ids(
                    self.session, subnet_id_settings.split(","), getattr(self, VPC_ID_T)
                ),
            )
        elif isinstance(subnet_id_settings, list):
            setattr(
                self,
                subnet_key,
                lookup_subnets_ids(
                    self.session, subnet_id_settings, getattr(self, VPC_ID_T)
                ),
            )
        elif (
            isinstance(subnet_id_settings, dict)
            and keyisset("tags", subnet_id_settings)
            and isinstance(subnet_id_settings["tags"], list)
        ):
            setattr(
                self,
                subnet_key,
                lookup_subnets_from_tags(
                    self.session,
                    subnet_id_settings["tags"],
                    getattr(self, VPC_ID_T),
                    subnet_key,
                ),
            )
        else:
            raise ValueError(
                "VpcId is neither the VPC ID, the VPC Arn or a set of tags"
            )

    def lookup_x_vpc_settings(self, settings):
        """
        Method to set VPC settings from x-vpc

        :param dict settings:
        :return:
        """
        required_keys = [VPC_ID_T, PUBLIC_SUBNETS_T, APP_SUBNETS_T, STORAGE_SUBNETS_T]
        subnets_keys = [PUBLIC_SUBNETS_T, APP_SUBNETS_T, STORAGE_SUBNETS_T]
        if not all(key in settings.keys() for key in required_keys):
            raise KeyError(
                "Missing keys for x-vpc Lookup. Got",
                settings.keys(),
                "Expected",
                required_keys,
            )
        self.lookup_vpc = True
        self.lookup_vpc_id(settings[VPC_ID_T])
        for subnet_key in subnets_keys:
            self.lookup_subnets_ids(subnet_key, settings[subnet_key])

    def set_x_vpc_settings(self, settings):
        """
        Method to set VpcCreate from x-vpc

        :param dict settings:
        :return:
        """
        self.single_nat = (
            settings[self.single_nat_arg]
            if keyisset(self.single_nat_arg, settings)
            else True
        )
        self.vpc_cidr = (
            settings[self.vpc_cidr_arg]
            if keyisset(self.vpc_cidr_arg, settings)
            else self.default_vpc_cidr
        )

    def set_vpc_defaults(self, kwargs):
        """
        Method to set the values of subnets if present in kwargs

        :param dict kwargs:
        :return:
        """
        self.create_vpc = True
        self.vpc_cidr = self.default_vpc_cidr
        self.single_nat = True
        setattr(self, VPC_ID_T, None)
        setattr(self, APP_SUBNETS_T, None)
        setattr(self, STORAGE_SUBNETS_T, None)
        setattr(self, PUBLIC_SUBNETS_T, None)

    def set_vpc_default_settings(self):
        LOG.info(
            f"Setting default VPC settings. Creating VPC and VPC CIDR is {self.default_vpc_cidr}"
        )
        self.create_vpc = True
        self.vpc_cidr = self.default_vpc_cidr

    def get_vpc_params(self):
        return {
            APP_SUBNETS_T: getattr(self, APP_SUBNETS_T),
            STORAGE_SUBNETS_T: getattr(self, STORAGE_SUBNETS_T),
            PUBLIC_SUBNETS_T: getattr(self, PUBLIC_SUBNETS_T),
            VPC_ID_T: getattr(self, VPC_ID_T),
        }

    def set_azs_from_api(self):
        """
        Method to set the AWS Azs based on DescribeAvailabilityZones
        :return:
        """
        try:
            self.aws_azs = get_region_azs(self.session)
        except ClientError as error:
            code = error.response["Error"]["Code"]
            message = error.response["Error"]["Message"]
            if code == "RequestExpired":
                LOG.error(message)
                LOG.warning(f"Due to error, using default values {self.aws_azs}")

            else:
                LOG.error(error)

    def set_bucket_name_from_account_id(self):
        if self.bucket_name and isinstance(self.bucket_name, str):
            return
        if self.account_id is None:
            try:
                self.account_id = get_account_id(session=self.session)
                self.bucket_name = f"ecs-composex-{self.account_id}-{self.aws_region}"
            except ClientError as error:
                code = error.response["Error"]["Code"]
                message = error.response["Error"]["Message"]
                if code == "ExpiredToken":
                    LOG.error(message)
                    LOG.warning(
                        f"Due to credentials error, we won't attempt to upload to S3."
                    )
                else:
                    LOG.error(error)
                self.bucket_name = None
                self.upload = False
                self.no_upload = True
