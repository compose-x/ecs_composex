#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Console script for ecs_composex."""

import sys
import argparse
import warnings
from boto3 import session
from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    BUCKET_NAME, CURATED_AZS
)
from ecs_composex.common import KEYISSET
from ecs_composex.root import generate_full_template
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS_T, PUBLIC_SUBNETS_T, STORAGE_SUBNETS_T,
    VPC_ID_T, VPC_MAP_ID_T
)
from ecs_composex.ecs.ecs_params import LAUNCH_TYPE_T
from ecs_composex.compute.cluster_params import (
    CLUSTER_NAME_T, USE_FLEET_T
)


def validate_vpc_input(args):
    """Function to validate the VPC arguments are all present

    :param args: Parser arguments
    :type args: dict

    :raise: KeyError if missing argument when not creating VPC

    """
    nocreate_requirements = [
        PUBLIC_SUBNETS_T,
        APP_SUBNETS_T,
        STORAGE_SUBNETS_T,
        VPC_ID_T, VPC_MAP_ID_T
    ]
    if not KEYISSET('CreateVpc', args):
        for key in nocreate_requirements:
            if not KEYISSET(key, args):
                raise ValueError(f"If you want to use an existing VPC, you need {key}")
    else:
        for key in nocreate_requirements:
            if KEYISSET(key, args):
                LOG.info(args[key])
                warnings.warn(
                    f"Creating VPC is set but you also set {key}. Ignoring and using new VPC values",
                    UserWarning
                )


def validate_cluster_input(args):
    """Function to validate the cluster arguments

    :param args: Parser arguments
    """
    if not KEYISSET('CreateCluster', args) and not KEYISSET(CLUSTER_NAME_T, args):
        raise KeyError(f"You must provide an ECS Cluster name if you do not want ECS ComposeX to create one for you")


def main():
    """Console script for ecs_composex."""
    parser = argparse.ArgumentParser()
    #  Generic settings
    parser.add_argument(
        '-f', '--docker-compose-file', dest='ComposeXFile',
        required=True, help="Path to the Docker compose file"
    )
    parser.add_argument(
        '-o', '--output-file', type=str, required=True,
        help="The name and path of the main output file. If you specify extra arguments, it will create a parameters"
             " file as well for creating your CFN Stack"
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
        '--storage-subnets', required=False, dest=STORAGE_SUBNETS_T, action='append',
        help="List of Subnet IDs to use for the cluster when not creating VPC"
    )
    parser.add_argument(
        '--discovery-map-id', '--map', dest=VPC_MAP_ID_T, required=False, help="Service Discovery ID, ie. ns-xxx"
    )
    parser.add_argument(
        '--single-nat', dest='SingleNat', action='store_true',
        help="Whether you want a single NAT for your application subnets or not. Not recommended for production"
    )
    # CLUSTER SETTINGS
    parser.add_argument(
        '--create-cluster', required=False, default=False, action='store_true',
        help="Create an ECS Cluster for this deployment", dest='CreateCluster'
    )
    parser.add_argument(
        '--cluster-name', type=str, required=False, dest=CLUSTER_NAME_T,
        help='Override/Provide ECS Cluster name'
    )
    # COMPUTE SETTINGS
    parser.add_argument(
        '--use-fargate', required=False, default=False, action='store_true',
        dest=LAUNCH_TYPE_T, help="If you run Fargate only, no EC2 will be created"
    )
    parser.add_argument(
        '--use-spot-fleet', required=False, default=False, action='store_true',
        dest=USE_FLEET_T, help="Runs spotfleet for EC2. If used in combination "
                               "of --use-fargate, it will create an additional SpotFleet"
    )
    parser.add_argument(
        '--create-launch-template', dest='CreateLaunchTemplate', action='store_true',
        help='Whether you want to create a launch template to create EC2 resources for'
        ' to expand the ECS Cluster and run containers on EC2 instances you might have access to.'
    )
    #  ECS COMPOSEX SPECIALS
    parser.add_argument(
        '--iam-only', default=False, action='store_true', required=False,
        help="Generates only the IAM roles for the tasks"
    )

    parser.add_argument('_', nargs='*')
    args = parser.parse_args()

    validate_vpc_input(vars(args))
    validate_cluster_input(vars(args))

    print("Arguments: " + str(args._))
    generate_full_template(**vars(args))


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
