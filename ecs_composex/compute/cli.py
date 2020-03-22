#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module to generate a cluster template standalone or import create_cluster_template
elsewhere for nested cluster stack
"""

import argparse
import sys

from boto3 import session

from ecs_composex.compute import create_cluster_template
from ecs_composex.common.aws import CURATED_AZS, BUCKET_NAME
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T
from ecs_composex.vpc.vpc_params import (
    VPC_ID_T, APP_SUBNETS_T,
    PUBLIC_SUBNETS_T
)


def root_parser():
    """
    Function to create the VPC specific arguments for argparse
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--docker-compose-file', required=False
    )
    parser.add_argument(
        '-o', '--output-file', required=True, help="Output file"
    )
    #  AWS SETTINGS
    parser.add_argument(
        '--region', required=False, default=session.Session().region_name,
        dest='AwsRegion',
        help="Specify the region you want to build for"
             "default use default region from config or environment vars"
    )
    parser.add_argument(
        '--az', dest='AwsAzs', action='append', required=False, default=CURATED_AZS,
        help="List AZs you want to deploy to specifically within the region"
    )
    parser.add_argument(
        '-b', '--bucket-name', type=str, required=False, default=BUCKET_NAME,
        help='Bucket name to upload the templates to', dest='BucketName'
    )
    # VPC SETTINGS
    parser.add_argument(
        '--create-vpc', required=False, default=False, action='store_true',
        help="Create a VPC for this deployment", dest='CreateVpc'
    )
    parser.add_argument(
        '--vpc-cidr', required=False, default='192.168.36.0/22', dest='VpcCidr',
        help="Specify the VPC CIDR if you use --create-vpc"
    )
    parser.add_argument(
        '--vpc-id', dest=VPC_ID_T, required=False, type=str,
        help='Specify VPC ID when not creating one'
    )
    parser.add_argument(
        '--public-subnets', required=False, dest=PUBLIC_SUBNETS_T, action='append',
        help="List of Subnet IDs to use for the cluster when not creating VPC"
    )
    parser.add_argument(
        '--app-subnets', required=False, dest=APP_SUBNETS_T, action='append',
        help="List of Subnet IDs to use for the cluster when not creating VPC"
    )
    parser.add_argument(
        '--storage-subnets', required=False, dest=APP_SUBNETS_T, action='append',
        help="List of Subnet IDs to use for the cluster when not creating VPC"
    )
    # CLUSTER SETTINGS
    parser.add_argument(
        '--create-cluster', required=False, default=False, action='store_true',
        help="Create an ECS Cluster for this deployment", dest='CreateCluster'
    )
    parser.add_argument(
        '--cluster-name', dest=CLUSTER_NAME_T, required=False
    )
    parser.add_argument(
        '--use-spot-fleet', required=False, default=False, action='store_true',
        dest='UseSpotFleet',
        help="Runs spotfleet for EC2. If used in combination "
             "of --use-fargate, it will create an additional SpotFleet"
    )
    return parser


def main():
    """Console script for ecs_composex."""
    parser = root_parser()
    parser.add_argument('_', nargs='*')
    args = parser.parse_args()

    template = create_cluster_template(**vars(args))
    with open(args.output_file, 'w') as tpl_fd:
        if args.output_file.endswith('.yml') or args.output_file.endswith('.yaml'):
            tpl_fd.write(template.to_yaml())
        else:
            tpl_fd.write(template.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
