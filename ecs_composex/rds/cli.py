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
import argparse
import os
import sys

from ecs_composex.common.aws import get_account_id
from ecs_composex.common.ecs_composex import DIR_DEST
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.stacks import render_final_template
from ecs_composex.rds import create_rds_template

ACCOUNT_ID = get_account_id()
BUCKET_NAME = f"cfn-templates-{ACCOUNT_ID[:6]}"


def create_parser():
    """
    Function to create the parser
    :return: parser
    :rtype: argparse.ArgumentParser
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-file",
        required=False,
        default=f"{os.path.basename(os.path.dirname(__file__))}.yml",
        help="Output file. Extension determines the file format",
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
        "-b",
        "--bucket-name",
        type=str,
        required=False,
        default=BUCKET_NAME,
        help="Bucket name to upload the templates to",
        dest="BucketName",
    )
    parser.add_argument(
        "-f",
        "--compose-file",
        required=True,
        dest="ComposeXFile",
        help="Path to the Docker Compose / ComposeX file",
    )
    parser.add_argument("_", nargs="*")
    return parser


def main():
    """
    Main function for CLI execution
    :return:
    """
    parser = create_parser()
    pargs = parser.parse_args()
    args = vars(pargs)
    template = create_rds_template(**args)
    if template:
        render_final_template(template)
        template_file = FileArtifact(pargs.output_file, template=template, **args)
        template_file.create()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
