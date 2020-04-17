#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Console script for ecs_composex.vpc"""

import sys
import argparse
from boto3 import session

from ecs_composex.common.aws import CURATED_AZS, BUCKET_NAME
from ecs_composex.vpc import create_vpc_template
from ecs_composex import XFILE_DEST, DIR_DEST
from ecs_composex.common.templates import FileArtifact


def main():
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
        default=CURATED_AZS,
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
        "--no-upload",
        action="store_true",
        default=False,
        help="Do not upload the file to S3.",
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
    parser.add_argument("_", nargs="*")
    args = parser.parse_args()

    template = create_vpc_template(**vars(args))
    file_name = "vpc.yml"
    if args.output_file:
        file_name = args.output_file
    template_file = FileArtifact(file_name, template=template, **vars(args))
    template_file.write()
    if not args.no_upload:
        template_file.upload()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
