# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Console script for ecs_composex.
"""

import argparse
import logging
import sys
import warnings

from ecs_composex.common.aws import deploy, plan
from ecs_composex.common.logging import LOG
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import process_stacks
from ecs_composex.compose.compose_services.service_image.docker_opts import (
    evaluate_ecr_configs,
)
from ecs_composex.ecs_composex import generate_full_template


class ArgparseHelper(argparse._HelpAction):
    """
    Used to help print top level '--help' arguments from argparse
    when used with subparsers
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
        "-h",
        "--help",
        action=ArgparseHelper,
        help="show this help message and exit",
    )

    cmd_parsers = parser.add_subparsers(
        dest=ComposeXSettings.command_arg, help="Command to execute."
    )
    base_command_parser = argparse.ArgumentParser(add_help=False)
    files_parser = argparse.ArgumentParser(add_help=False)
    extras_parser = argparse.ArgumentParser(add_help=False)
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
        "-p",
        "--name",
        help="Name of your stack / docker project",
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
    base_command_parser.add_argument(
        "--region",
        required=False,
        dest=ComposeXSettings.region_arg,
        help="Specify the region you want to build for"
        "default use default region from config or environment vars",
    )
    base_command_parser.add_argument(
        "--azs",
        dest=ComposeXSettings.zones_arg,
        default=[],
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
    base_command_parser.add_argument(
        "--role-arn",
        dest=ComposeXSettings.arn_arg,
        help="Allow you to run API calls using a specific IAM role, within same or for cross-account",
        required=False,
    )
    base_command_parser.add_argument(
        "--disable-rollback",
        dest="DisableRollback",
        help="On create/plan, disable stack automatic rollback.",
        required=False,
        action="store_true",
    )
    extras_parser.add_argument(
        "--ignore-ecr-findings",
        dest=ComposeXSettings.ecr_arg,
        action="store_true",
        default=False,
        help="For services with x-ecr defined, ignores errors if any found",
    )
    base_command_parser.add_argument(
        "--loglevel", type=str, help="Log level. Defaults to INFO", required=False
    )
    for command in ComposeXSettings.active_commands:
        cmd_parsers.add_parser(
            name=command["name"],
            help=command["help"],
            parents=[base_command_parser, files_parser, extras_parser],
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
    if args.loglevel:
        valid_levels = [
            "FATAL",
            "CRITICAL",
            "ERROR",
            "WARNING",
            "WARN",
            "INFO",
            "DEBUG",
            "INFO",
        ]
        if args.loglevel.upper() in valid_levels:
            LOG.setLevel(logging.getLevelName(args.loglevel.upper()))
            LOG.handlers[0].setLevel(logging.getLevelName(args.loglevel.upper()))
        else:
            print(
                f"Log level value {args.loglevel} is invalid. Must me one of {valid_levels}"
            )
    LOG.debug(args)
    settings = ComposeXSettings(**vars(args))
    settings.set_bucket_name_from_account_id()
    LOG.debug(settings)

    if settings.deploy and not settings.upload:
        LOG.warning(
            "You must update the templates in order to deploy. We won't be deploying."
        )
        settings.deploy = False
    scan_results = evaluate_ecr_configs(settings)
    if scan_results and not settings.ignore_ecr_findings:
        warnings.warn("SCAN Images failed for instructed images. Failure")
        return 1
    root_stack = generate_full_template(settings)
    process_stacks(root_stack, settings)

    if settings.deploy:
        deploy(settings, root_stack)
    elif settings.plan:
        plan(settings, root_stack)
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
