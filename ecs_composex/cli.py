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

"""Console script for ecs_composex."""

import argparse
import sys

from ecs_composex.common import LOG
from ecs_composex.common.aws import deploy
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import process_stacks
from ecs_composex.ecs_composex import generate_full_template


class ArgparseHelper(argparse._HelpAction):
    """
    Used to help print top level '--help' arguments from argparse
    when used with subparsers

    Usage:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-h', '--help', action=ArgparseHelper,
                        help='show this help message and exit')
    """

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()
        print()
        subparsers_actions = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        for subparsers_action in subparsers_actions:
            for choice, subparser in list(subparsers_action.choices.items()):
                if choice in [
                    cmd["name"] for cmd in ComposeXSettings.active_commands
                ] or choice in [
                    cmd["name"] for cmd in ComposeXSettings.validation_commands
                ]:
                    print(f"Command '{choice}'")
                    print(subparser.format_usage())


def main_parser():
    """
    Console script for ecs_composex.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-h", "--help", action=ArgparseHelper, help="show this help message and exit"
    )
    cmd_parsers = parser.add_subparsers(
        dest=ComposeXSettings.command_arg, help="Command to execute."
    )
    base_command_parser = argparse.ArgumentParser(add_help=False)
    files_parser = argparse.ArgumentParser(add_help=False)
    files_parser.add_argument(
        "-f",
        "--docker-compose-file",
        dest=ComposeXSettings.input_file_arg,
        required=True,
        help="Path to the Docker compose file",
        action="append",
    )
    files_parser.add_argument(
        "-d",
        "--output-dir",
        required=False,
        help="Output directory to write all the templates to.",
        type=str,
        dest=ComposeXSettings.output_dir_arg,
        default=ComposeXSettings.default_output_dir,
    )
    base_command_parser.add_argument(
        "-n",
        "--name",
        help="Name of your stack",
        required=True,
        type=str,
        dest=ComposeXSettings.name_arg,
    )
    base_command_parser.add_argument(
        "--format",
        help="Defines the format you want to use.",
        type=str,
        dest=ComposeXSettings.format_arg,
        choices=ComposeXSettings.allowed_formats,
        default=ComposeXSettings.default_format,
    )
    #  AWS SETTINGS
    base_command_parser.add_argument(
        "--region",
        required=False,
        dest=ComposeXSettings.region_arg,
        help="Specify the region you want to build for"
        "default use default region from config or environment vars",
    )
    base_command_parser.add_argument(
        "--az",
        dest=ComposeXSettings.zones_arg,
        default=ComposeXSettings.default_azs,
        action="append",
        required=False,
        help="List AZs you want to deploy to specifically within the region",
    )
    base_command_parser.add_argument(
        "-b",
        "--bucket-name",
        type=str,
        required=False,
        help="Bucket name to upload the templates to",
        dest="BucketName",
    )
    # COMPUTE SETTINGS
    base_command_parser.add_argument(
        "--use-spot-fleet",
        required=False,
        default=False,
        action="store_true",
        dest=ComposeXSettings.create_spotfleet_arg,
        help="Runs spotfleet for EC2. If used in combination "
        "of --use-fargate, it will create an additional SpotFleet",
    )
    for command in ComposeXSettings.active_commands:
        cmd_parsers.add_parser(
            name=command["name"],
            help=command["help"],
            parents=[base_command_parser, files_parser],
        )
    for command in ComposeXSettings.validation_commands:
        cmd_parsers.add_parser(
            name=command["name"], help=command["help"], parents=[files_parser]
        )

    for command in ComposeXSettings.neutral_commands:
        cmd_parsers.add_parser(name=command["name"], help=command["help"])
    return parser


def main():
    """
    Main entry point for CLI
    :return: status code
    """
    parser = main_parser()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()
    args = parser.parse_args()
    LOG.debug(args)
    settings = ComposeXSettings(**vars(args))
    settings.set_bucket_name_from_account_id()
    settings.set_azs_from_api()
    LOG.debug(settings)

    if settings.deploy and not settings.upload:
        LOG.warning(
            "You must update the templates in order to deploy. We won't be deploying."
        )
        settings.deploy = False

    root_stack = generate_full_template(settings)
    process_stacks(root_stack, settings)

    if settings.deploy:
        deploy(settings, root_stack)
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
