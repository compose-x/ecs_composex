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

"""Console script for ecs_composex.sns"""
import argparse
import os
import sys

from ecs_composex.common import load_composex_file, validate_kwargs, validate_input
from ecs_composex.common.aws import get_account_id
from ecs_composex.common.ecs_composex import XFILE_DEST, DIR_DEST
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.stacks import render_final_template
from ecs_composex.sns import generate_sns_templates

ACCOUNT_ID = get_account_id()
BUCKET_NAME = f"cfn-templates-{ACCOUNT_ID[:6]}"


def sqs_parser():
    """Console script for ecs_composex."""
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
    parser.add_argument(
        "--no-upload",
        action="store_true",
        default=False,
        help="Whether the templates should be uploaded or not.",
        dest="NoUpload",
    )

    parser.add_argument("_", nargs="*")
    return parser


def main():
    """
    Main function to invoke ecs_composex-sqs CLI
    :return:
    """
    res_key = f"x-{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}"
    parser = sqs_parser()
    args = parser.parse_args()
    kwargs = vars(args)
    content = load_composex_file(kwargs[XFILE_DEST])
    validate_input(content, res_key)
    validate_kwargs(["BucketName"], kwargs)
    template = generate_sns_templates(content, **kwargs)
    render_final_template(template)
    template_file = FileArtifact(args.output_file, template=template, **vars(args))
    template_file.create()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
