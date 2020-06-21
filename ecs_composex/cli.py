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
import os
import sys
import warnings

from boto3 import session

from ecs_composex.common import keyisset
from ecs_composex.common import LOG, load_composex_file
from ecs_composex.common.aws import get_account_id
from ecs_composex.common.cfn_params import USE_FLEET_T
from ecs_composex.common.cfn_tools import build_config_template_file
from ecs_composex.common.ecs_composex import XFILE_DEST, DIR_DEST
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.stacks import render_final_template
from ecs_composex.compute.compute_params import CLUSTER_NAME_T
from ecs_composex.ecs_composex import generate_full_template
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS_T,
    PUBLIC_SUBNETS_T,
    STORAGE_SUBNETS_T,
    VPC_ID_T,
    VPC_MAP_ID_T,
)

ACCOUNT_ID = get_account_id()
BUCKET_NAME = f"cfn-templates-{ACCOUNT_ID[:6]}"


def validate_vpc_input(args):
    """
    Function to validate the VPC arguments are all present

    :param args: Parser arguments
    :type args: dict

    :raise: KeyError if missing argument when not creating VPC

    """
    nocreate_requirements = [
        PUBLIC_SUBNETS_T,
        APP_SUBNETS_T,
        STORAGE_SUBNETS_T,
        VPC_ID_T,
        VPC_MAP_ID_T,
    ]
    if not keyisset("CreateVpc", args):
        for key in nocreate_requirements:
            if not keyisset(key, args):
                warnings.warn(
                    f"{key} was not provided. Not adding to the parameters file",
                    UserWarning,
                )
    else:
        for key in nocreate_requirements:
            if keyisset(key, args):
                LOG.info(args[key])
                warnings.warn(
                    f"Creating VPC is set. Ignoring value for {key}", UserWarning
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
        "-f",
        "--docker-compose-file",
        dest=XFILE_DEST,
        required=True,
        help="Path to the Docker compose file",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        required=False,
        default=f"{os.path.basename(os.path.dirname(__file__))}.yml",
        help="Output file. Extension determines the file format",
    )
    parser.add_argument(
        "-d",
        "--output-dir",
        required=False,
        help="Output directory to write all the templates to.",
        type=str,
        dest=DIR_DEST,
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
        default=session.Session().region_name,
        dest="AwsRegion",
        help="Specify the region you want to build for"
        "default use default region from config or environment vars",
    )
    parser.add_argument(
        "--az",
        dest="AwsAzs",
        action="append",
        required=False,
        default=[],
        help="List AZs you want to deploy to specifically within the region",
    )
    parser.add_argument(
        "-b",
        "--bucket-name",
        type=str,
        required=False,
        default=BUCKET_NAME,
        help="Bucket name to upload the templates to",
        dest="BucketName",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        default=False,
        help="Whether the templates should be uploaded or not.",
        dest="NoUpload",
    )
    # VPC SETTINGS
    parser.add_argument(
        "--create-vpc",
        required=False,
        default=False,
        action="store_true",
        help="Create a VPC for this deployment",
        dest="CreateVpc",
    )
    parser.add_argument(
        "--vpc-cidr",
        required=False,
        default="192.168.36.0/22",
        dest="VpcCidr",
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
        "--map",
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
        dest=USE_FLEET_T,
        help="Runs spotfleet for EC2. If used in combination "
        "of --use-fargate, it will create an additional SpotFleet",
    )
    parser.add_argument(
        "--add-compute-resources",
        dest="AddComputeResources",
        action="store_true",
        help="Whether you want to create a launch template to create EC2 resources for"
        " to expand the ECS Cluster and run containers on EC2 instances you might have access to.",
    )
    #  ECS COMPOSEX SPECIALS
    parser.add_argument(
        "--iam-only",
        default=False,
        action="store_true",
        required=False,
        help="Generates only the IAM roles for the tasks",
    )

    parser.add_argument("_", nargs="*")
    return parser


def main():
    parser = main_parser()
    args = parser.parse_args()

    kwargs = vars(args)
    content = load_composex_file(kwargs[XFILE_DEST])
    validate_vpc_input(vars(args))
    validate_cluster_input(vars(args))

    print("Arguments: " + str(args._))
    templates_and_params = generate_full_template(content, **kwargs)

    render_final_template(templates_and_params[0])
    cfn_config = build_config_template_file(
        config={}, parameters=templates_and_params[1]
    )
    if keyisset("CfnConfigFile", vars(args)):
        config_file_name = args.CfnConfigFile
    else:
        config_file_name = f"{args.output_file.split('.')[0]}.config.json"
    config_file = FileArtifact(config_file_name, content=cfn_config, **vars(args))
    params_file = FileArtifact(
        f"{args.output_file.split('.')[0]}.params.json",
        content=templates_and_params[1],
        **vars(args),
    )
    template_file = FileArtifact(
        args.output_file, template=templates_and_params[0], **vars(args)
    )
    template_file.create()
    params_file.create()
    config_file.create()


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
