#!/usr/bin/env python
# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Console script for ecs_composex."""

import argparse
import sys
import warnings

from ecs_composex.common import LOG
from ecs_composex.common import keyisset
from ecs_composex.common.aws import deploy
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import process_stacks
from ecs_composex.compute.compute_params import CLUSTER_NAME_T
from ecs_composex.ecs_composex import generate_full_template
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS_T,
    PUBLIC_SUBNETS_T,
    STORAGE_SUBNETS_T,
    VPC_ID_T,
    VPC_MAP_ID_T,
)


def validate_cluster_input(args):
    """Function to validate the cluster arguments

    :param args: Parser arguments
    :raise: KeyError
    """
    if not keyisset("CreateCluster", args) and not keyisset(CLUSTER_NAME_T, args):
        warnings.warn(
            f"You must provide an ECS Cluster name if you do not want ECS ComposeX to create one for you",
            UserWarning,
        )


def main_parser():
    """
    Console script for ecs_composex.
    """
    SUBNETS_DESC = "List of Subnet IDs to use for the cluster when not creating VPC"
    parser = argparse.ArgumentParser()
    #  Generic settings
    parser.add_argument(
        "-n",
        "--name",
        help="Name of your stack",
        required=True,
        type=str,
        dest=ComposeXSettings.name_arg,
    )
    parser.add_argument(
        "-f",
        "--docker-compose-file",
        dest=ComposeXSettings.input_file_arg,
        required=True,
        help="Path to the Docker compose file",
    )
    parser.add_argument(
        "-d",
        "--output-dir",
        required=False,
        help="Output directory to write all the templates to.",
        type=str,
        dest=ComposeXSettings.output_dir_arg,
        default=ComposeXSettings.default_output_dir,
    )
    parser.add_argument(
        "--format",
        help="Defines the format you want to use.",
        type=str,
        dest=ComposeXSettings.format_arg,
        choices=ComposeXSettings.allowed_formats,
        default=ComposeXSettings.default_format,
    )
    parser.add_argument(
        "--cfn-config-file",
        help="Path to AWS Template config file",
        required=False,
        dest="CfnConfigFile",
        type=str,
    )
    parser.add_argument(
        "--no-cfn-template-config-file",
        action="store_true",
        default=True,
        help="Do not generate the CFN Configuration template file",
    )
    #  AWS SETTINGS
    parser.add_argument(
        "--region",
        required=False,
        dest=ComposeXSettings.region_arg,
        help="Specify the region you want to build for"
        "default use default region from config or environment vars",
    )
    parser.add_argument(
        "--az",
        dest=ComposeXSettings.zones_arg,
        default=ComposeXSettings.default_azs,
        action="append",
        required=False,
        help="List AZs you want to deploy to specifically within the region",
    )
    parser.add_argument(
        "-b",
        "--bucket-name",
        type=str,
        required=False,
        help="Bucket name to upload the templates to",
        dest="BucketName",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        default=False,
        help="Whether the templates should be uploaded or not.",
        dest=ComposeXSettings.no_upload_arg,
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        default=False,
        required=False,
        help="Whether or not you would like to deploy the stack to CFN.",
        dest=ComposeXSettings.deploy_arg,
    )
    # VPC SETTINGS
    parser.add_argument(
        "--create-vpc",
        required=False,
        default=False,
        action="store_true",
        help="Create a VPC for this deployment",
        dest=ComposeXSettings.create_vpc_arg,
    )
    parser.add_argument(
        "--vpc-cidr",
        required=False,
        default=ComposeXSettings.default_vpc_cidr,
        dest=ComposeXSettings.vpc_cidr_arg,
        help="Specify the VPC CIDR if you use --create-vpc",
    )
    parser.add_argument(
        "--vpc-id",
        dest=VPC_ID_T,
        required=False,
        type=str,
        help="Specify VPC ID when not creating one",
    )
    parser.add_argument(
        "--public-subnets",
        required=False,
        dest=PUBLIC_SUBNETS_T,
        action="append",
        help=SUBNETS_DESC,
    )
    parser.add_argument(
        "--app-subnets",
        required=False,
        dest=APP_SUBNETS_T,
        action="append",
        help=SUBNETS_DESC,
    )
    parser.add_argument(
        "--storage-subnets",
        required=False,
        dest=STORAGE_SUBNETS_T,
        action="append",
        help=SUBNETS_DESC,
    )
    parser.add_argument(
        "--discovery-map-id",
        "--cloud-map-id",
        dest=VPC_MAP_ID_T,
        required=False,
        help="Service Discovery ID, ie. ns-xxx",
    )
    parser.add_argument(
        "--single-nat",
        dest="SingleNat",
        action="store_true",
        help="Whether you want a single NAT for your application subnets or not. Not recommended for production",
    )
    # CLUSTER SETTINGS
    parser.add_argument(
        "--create-cluster",
        required=False,
        default=False,
        action="store_true",
        help="Create an ECS Cluster for this deployment",
        dest="CreateCluster",
    )
    parser.add_argument(
        "--cluster-name",
        type=str,
        required=False,
        dest=CLUSTER_NAME_T,
        help="Override/Provide ECS Cluster name",
    )
    # COMPUTE SETTINGS
    parser.add_argument(
        "--use-spot-fleet",
        required=False,
        default=False,
        action="store_true",
        dest=ComposeXSettings.create_spotfleet_arg,
        help="Runs spotfleet for EC2. If used in combination "
        "of --use-fargate, it will create an additional SpotFleet",
    )

    parser.add_argument("_", nargs="*")
    return parser


def main():
    parser = main_parser()
    args = parser.parse_args()
    settings = ComposeXSettings(**vars(args))
    settings.set_bucket_name_from_account_id()
    settings.set_azs_from_api()
    LOG.debug(settings)

    if settings.deploy and not settings.upload:
        LOG.warning(
            "You must update the templates in order to deploy. We won't be deploying."
        )
        settings.deploy = False

    # validate_vpc_input(settings)
    validate_cluster_input(vars(args))

    root_stack = generate_full_template(settings)
    process_stacks(root_stack, settings)

    if settings.deploy:
        deploy(settings, root_stack)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
