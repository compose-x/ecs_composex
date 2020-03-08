#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Console script for ecs_composex.vpc"""

import sys
import argparse
from boto3 import session

from ecs_composex.common.aws import CURATED_AZS
from ecs_composex.vpc import create_vpc_template


def main():
    """Console script for ecs_composex."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--vpc-cidr', required=False, default='192.168.36.0/22', dest='VpcCidr',
        help="Specify the VPC CIDR"
    )
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
        '-o', '--output-file', required=True,
        help="Output file for the template body"
    )
    parser.add_argument(
        '--single-nat', dest='SingleNat', action='store_true',
        help="Whether you want a single NAT for your application subnets or not. Not recommended for production"
    )
    parser.add_argument('_', nargs='*')
    args = parser.parse_args()

    template = create_vpc_template(**vars(args))
    if args.output_file:
        with open(args.output_file, 'w') as tpl_fd:
            if args.output_file.endswith('.yml') or args.output_file.endswith('.yaml'):
                tpl_fd.write(template.to_yaml())
            else:
                tpl_fd.write(template.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
