#!/usr/bin/env python
# -*- coding: utf-8 -
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

"""Console script for ecs_composex.sqs"""
import sys
import os

from ecs_composex.cli import main_parser
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import process_stacks
from ecs_composex.rds.rds_stack import XResource


def main():
    """
    Main function for CLI execution
    :return:
    """
    res_key = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
    parser = main_parser()
    args = parser.parse_args()

    settings = ComposeXSettings(**vars(args))
    settings.set_bucket_name_from_account_id()
    settings.set_azs_from_api()

    sns_stack = XResource(res_key, settings)
    process_stacks(sns_stack, settings)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
