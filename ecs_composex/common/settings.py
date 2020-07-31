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
Module for the ComposeXSettings class
"""

from datetime import datetime as dt
from json import dumps

import boto3
from botocore.exceptions import ClientError

from ecs_composex import __version__
from ecs_composex.common import keyisset, LOG, load_composex_file
from ecs_composex.common.aws import get_account_id, get_region_azs
from ecs_composex.common.cfn_params import USE_FLEET_T
from ecs_composex.utils.init_ecs import set_ecs_settings
from ecs_composex.utils.init_s3 import create_bucket


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

    commands = [
        {
            "name": "up",
            "help": "Generates & Validates the CFN templates, Creates/Updates stack in CFN",
        },
        {
            "name": "config",
            "help": "Generates & Validates the CFN templates locally. No upload to S3.",
        },
        {"name": "version", "help": "ECS ComposeX Version"},
    ]
    neutral_commands = [
        {
            "name": "init",
            "help": "Initializes your AWS Account with prerequisites settings for ECS",
        },
        {"name": "version", "help": "ECS ComposeX Version"},
    ]

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

        self.bucket_name = (
            None if not keyisset(self.bucket_arg, kwargs) else kwargs[self.bucket_arg]
        )
        self.account_id = None
        self.output_dir = self.default_output_dir
        self.format = self.default_format

        self.create_vpc = False
        self.vpc_cidr = None
        self.single_nat = None
        self.lookup_vpc = False
        self.deploy = True if keyisset(self.deploy_arg, kwargs) else False
        self.no_upload = True if keyisset(self.no_upload_arg, kwargs) else False

        self.upload = False if self.no_upload else True
        self.create_compute = False if not keyisset(USE_FLEET_T, kwargs) else True
        self.parse_command(kwargs)

        if content is None:
            self.compose_content = load_composex_file(kwargs[self.input_file_arg])
        elif content and isinstance(content, dict):
            self.compose_content = content

        self.input_file = (
            kwargs[self.input_file_arg] if keyisset(self.input_file_arg, kwargs) else {}
        )

        self.set_output_settings(kwargs)
        self.name = kwargs[self.name_arg]

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
        command_names = [cmd["name"] for cmd in self.commands] + [
            cmd["name"] for cmd in self.neutral_commands
        ]
        if command not in command_names:
            exit(1)
        if command == self.deploy_arg:
            self.deploy = True
            self.upload = True
        elif command == self.no_upload_arg:
            self.no_upload = True
            self.upload = not self.no_upload
        elif command == "version":
            print("ECS ComposeX", __version__)
            exit(0)
        elif command == "init":
            set_ecs_settings(self.session)
            self.init_s3()
            exit(0)

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

    def init_s3(self):
        """
        Method to initialize S3 settings

        :return:
        """
        self.set_bucket_name_from_account_id()
        if self.bucket_name:
            create_bucket(self.bucket_name, self.session)
