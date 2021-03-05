# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only

"""Console script for ecs_composex.vpc"""

import sys

from ecs_composex.cli import main_parser
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import process_stacks
from ecs_composex.vpc.vpc_stack import VpcStack
from ecs_composex.vpc.vpc_params import RES_KEY
from ecs_composex.common.aws import deploy


def main():
    """
    Main Function
    :return:
    """
    parser = main_parser()
    args = parser.parse_args()
    settings = ComposeXSettings(**vars(args))
    settings.set_bucket_name_from_account_id()
    settings.set_azs_from_api()

    vpc_stack = VpcStack(RES_KEY, settings)
    process_stacks(vpc_stack, settings)
    if settings.deploy:
        deploy(settings, vpc_stack)
    return 0


if __name__ == "__main__":
    sys.exit(main())
