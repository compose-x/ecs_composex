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
    sys.exit(main())  # pragma: no cover
