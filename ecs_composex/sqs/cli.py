#!/usr/bin/env python
# -*- coding: utf-8 -

"""Console script for ecs_composex.sqs"""
import sys
import os
import argparse
import boto3

from ecs_composex.common.ecs_composex import XFILE_DEST, DIR_DEST
from ecs_composex.common.aws import get_account_id
from ecs_composex.common import load_composex_file, validate_kwargs, validate_input
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.stacks import render_final_template
from ecs_composex.sqs.sqs_template import generate_sqs_root_template

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
    session = boto3.session.Session()
    template = generate_sqs_root_template(
        compose_content=content, session=session, **kwargs
    )

    render_final_template(template)
    template_file = FileArtifact(args.output_file, template=template, **vars(args))
    template_file.create()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
