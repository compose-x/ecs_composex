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

import boto3
from botocore.exceptions import ClientError
from json import dumps
from datetime import datetime as dt

from ecs_composex.common import keyisset, LOG, load_composex_file
from ecs_composex.common.aws import get_account_id, get_region_azs
from ecs_composex.vpc.vpc_params import (
    VPC_ID_T,
    PUBLIC_SUBNETS_T,
    APP_SUBNETS_T,
    STORAGE_SUBNETS_T,
    VPC_MAP_ID_T,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.common.cfn_params import USE_FLEET_T


class ComposeXSettings(object):
    """
    Class to handle the settings to use for ECS ComposeX.
    """

    name_arg = "Name"
    cluster_name_arg = "ClusterName"

    create_cluster_arg = "CreateCluster"
    create_vpc_arg = "CreateVpc"
    create_ec2_arg = "AddComputeResources"
    create_spotfleet_arg = USE_FLEET_T

    region_arg = "RegionName"
    zones_arg = "Zones"
    deploy_arg = "DeployToCfn"

    bucket_arg = "BucketName"
    no_upload_arg = "NoUpload"
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

    def __init__(self, profile_name=None, session=None, **kwargs):
        """
        Class to init the configuration
        """
        if profile_name and not session:
            self.session = boto3.session.Session(profile_name=profile_name)
        elif session and not profile_name:
            self.session = session
        else:
            self.session = boto3.session.Session()

        self.aws_region = (
            kwargs[self.region_arg]
            if keyisset(self.region_arg, kwargs)
            else self.session.region_name
        )
        self.aws_azs = self.default_azs
        self.compose_content = load_composex_file(kwargs[self.input_file_arg])
        self.account_id = None

        self.bucket_name = None
        self.output_dir = self.default_output_dir
        self.format = self.default_format
        self.set_output_settings(kwargs)

        self.no_upload = True if keyisset(self.no_upload_arg, kwargs) else False
        self.upload = False if self.no_upload else True
        self.name = kwargs[self.name_arg]
        self.create_compute = False if not keyisset(USE_FLEET_T, kwargs) else True

        self.vpc_id = None
        self.vpc_cidr = self.default_vpc_cidr
        self.app_subnets = None
        self.storage_subnets = None
        self.single_nat = None
        self.public_subnets = None
        self.vpc_private_namespace_id = None
        self.vpc_private_namespace_zone_id = None
        self.vpc_private_namespace_tld = None
        self.create_vpc = False
        self.set_vpc_settings(kwargs)

        self.create_cluster = None
        self.cluster_name = None
        self.set_cluster_settings(kwargs)
        self.deploy = True if keyisset(self.deploy_arg, kwargs) else False

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

    def set_cluster_settings(self, kwargs):
        """
        Method to set cluster settings based on kwargs
        """
        self.create_cluster = (
            True if keyisset(self.create_cluster_arg, kwargs) else False
        )
        self.cluster_name = (
            kwargs[self.cluster_name_arg]
            if keyisset(self.cluster_name_arg, kwargs)
            else None
        )

    def set_vpc_settings(self, kwargs):
        """
        Method to set the values of subnets if present in kwargs
        :param kwargs:
        :return:
        """
        self.vpc_cidr = (
            kwargs[self.vpc_cidr_arg]
            if keyisset(self.vpc_cidr_arg, kwargs)
            else self.default_vpc_cidr
        )
        self.create_vpc = True if keyisset(self.create_vpc_arg, kwargs) else False
        self.vpc_id = kwargs[VPC_ID_T] if keyisset(VPC_ID_T, kwargs) else None
        self.single_nat = (
            kwargs[self.single_nat_arg]
            if keyisset(self.single_nat_arg, kwargs)
            else True
        )
        self.public_subnets = (
            kwargs[PUBLIC_SUBNETS_T] if keyisset(PUBLIC_SUBNETS_T, kwargs) else None
        )
        self.storage_subnets = (
            kwargs[STORAGE_SUBNETS_T] if keyisset(STORAGE_SUBNETS_T, kwargs) else None
        )
        self.app_subnets = (
            kwargs[APP_SUBNETS_T] if keyisset(APP_SUBNETS_T, kwargs) else None
        )
        self.vpc_private_namespace_id = (
            kwargs[VPC_MAP_ID_T] if keyisset(VPC_MAP_ID_T, kwargs) else None
        )
        if self.vpc_private_namespace_id:
            client = self.session.client("servicediscovery")
            try:
                res = client.get_namespace(Id=self.vpc_private_namespace_id)
                self.vpc_private_namespace_zone_id = res["Namespace"]["Properties"][
                    "DnsProperties"
                ]["HostedZoneId"]
                self.vpc_private_namespace_tld = res["Namespace"]["Properties"][
                    "HttpProperties"
                ]["HttpName"]

            except client.meta.exceptions.NamespaceNotFound as error:
                LOG.error(
                    f"Namespace {self.vpc_private_namespace_id} not found in this account."
                )
                raise error

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

    def create_root_stack_parameters_from_input(self):
        """
        Method to create the parameters for the root stack from CLI input.
        :return:
        """
        parameters = {}
        if self.cluster_name != CLUSTER_NAME.Default:
            parameters[CLUSTER_NAME.title] = self.cluster_name
        return parameters
