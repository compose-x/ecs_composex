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

"""
Module to generate a cluster template standalone or import create_cluster_template
elsewhere for nested cluster stack
"""

import argparse
import sys
import os

from boto3 import session
from ecs_composex.common.ecs_composex import XFILE_DEST, DIR_DEST
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.aws import get_curated_azs, get_account_id
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T
from ecs_composex.vpc.vpc_params import VPC_ID_T, APP_SUBNETS_T
from ecs_composex.compute import create_compute_stack
from ecs_composex.common.cfn_params import USE_FLEET_T

CURATED_AZS = get_curated_azs()
ACCOUNT_ID = get_account_id()
BUCKET_NAME = f"cfn-templates-{ACCOUNT_ID[:6]}"


def root_parser():
    """
    Function to create the VPC specific arguments for argparse
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--docker-compose-file",
        required=False,
        dest=XFILE_DEST,
        help="Optionally use the YAML ComposeX file to add options and settings",
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
        default=CURATED_AZS,
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
    # VPC SETTINGS
    parser.add_argument(
        "--vpc-id",
        dest=VPC_ID_T,
        required=False,
        type=str,
        help="Specify VPC ID when not creating one",
    )
    parser.add_argument(
        "--hosts-subnets",
        required=False,
        dest=APP_SUBNETS_T,
        action="append",
        help="List of Subnet IDs to use for the cluster when not creating VPC",
    )
    # CLUSTER SETTINGS
    parser.add_argument("--cluster-name", dest=CLUSTER_NAME_T, required=False)
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
        "--no-upload",
        action="store_true",
        default=False,
        help="Do not upload the file to S3.",
    )
    return parser


def main():
    """Console script for ecs_composex."""
    parser = root_parser()
    parser.add_argument("_", nargs="*")
    args = parser.parse_args()

    template_params = create_compute_stack(**vars(args))
    template_file = FileArtifact(
        args.output_file, template=template_params[0], **vars(args)
    )
    params_file_name = f"{args.output_file.split('.')[0]}.params.json"
    params_file = FileArtifact(
        params_file_name, content=template_params[1], **vars(args)
    )
    if args.no_upload:
        template_file.write()
        params_file.write()
    else:
        template_file.create()
        params_file.create()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
