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

"""Console script for ecs_composex.vpc"""

import sys
import argparse
from boto3 import session

from ecs_composex.common import LOG
from ecs_composex.common.aws import get_curated_azs, get_account_id
from ecs_composex.vpc import create_vpc_template
from ecs_composex.common.ecs_composex import XFILE_DEST, DIR_DEST
from ecs_composex.common.files import FileArtifact

CURATED_AZS = get_curated_azs()
ACCOUNT_ID = get_account_id()
BUCKET_NAME = f"cfn-templates-{ACCOUNT_ID[:6]}"


def vpc_parser():
    """Console script for ecs_composex."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vpc-cidr",
        required=False,
        default="192.168.36.0/22",
        dest="VpcCidr",
        help="Specify the VPC CIDR",
    )
    parser.add_argument("-f", "--composex-file", dest=XFILE_DEST, required=False)
    parser.add_argument(
        "--region",
        required=False,
        default=session.Session().region_name,
        dest="AwsRegion",
        help="Specify the region you want to build for"
        "default use default region from config or environment vars",
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
        "--az",
        dest="AwsAzs",
        action="append",
        required=False,
        default=[],
        help="List AZs you want to deploy to specifically within the region",
    )
    parser.add_argument(
        "-o", "--output-file", required=True, help="Output file for the template body"
    )
    parser.add_argument(
        "--single-nat",
        dest="SingleNat",
        action="store_true",
        help="Whether you want a single NAT for your application subnets or not. Not recommended for production",
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
    parser.add_argument("_", nargs="*")
    return parser


def main():
    """
    Main Function
    :return:
    """
    parser = vpc_parser()
    args = parser.parse_args()
    try:
        template = create_vpc_template(**vars(args))
        file_name = "vpc.yml"
        if args.output_file:
            file_name = args.output_file
        template_file = FileArtifact(file_name, template=template, **vars(args))
        template_file.create()
        return 0
    except Exception as error:
        LOG.error(error)
        return 1


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
