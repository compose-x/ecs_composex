#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module to generate a cluster template standalone or import create_cluster_template
elsewhere for nested cluster stack
"""

import argparse
import sys
import json

from boto3 import session
from ecs_composex import XFILE_DEST
from ecs_composex.common import write_template_to_file
from ecs_composex.common.aws import CURATED_AZS, BUCKET_NAME
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T
from ecs_composex.vpc.vpc_params import VPC_ID_T, APP_SUBNETS_T
from ecs_composex.compute import create_compute_stack
from ecs_composex.common.cfn_params import USE_FLEET_T


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
        required=True,
        help="Output file. Extension determines the file format",
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
    return parser


def main():
    """Console script for ecs_composex."""
    parser = root_parser()
    parser.add_argument("_", nargs="*")
    args = parser.parse_args()

    template_params = create_compute_stack(**vars(args))
    write_template_to_file(template_params[0], args.output_file)
    with open(f"{args.output_file.split('.')[0]}.params.json", 'w') as params_fd:
        params_fd.write(json.dumps(template_params[1], indent=4))
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
