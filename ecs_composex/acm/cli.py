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
CLI for ecs_composex.acm
"""

import argparse
import os
import sys

from boto3 import session

from ecs_composex.common.aws import get_curated_azs, get_account_id
from ecs_composex.common.ecs_composex import XFILE_DEST, DIR_DEST
from ecs_composex.common.files import FileArtifact
from ecs_composex.acm import create_acm_template
from ecs_composex.common.stacks import render_final_template

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
        help="Do not upload the file to S3.",
    )
    return parser


def main():
    """Console script for ecs_composex."""
    parser = root_parser()
    parser.add_argument("_", nargs="*")
    args = parser.parse_args()

    template = create_acm_template(**vars(args))
    render_final_template(template)
    template_file = FileArtifact(args.output_file, template=template, **vars(args))
    if args.no_upload:
        template_file.write()
    else:
        template_file.create()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
