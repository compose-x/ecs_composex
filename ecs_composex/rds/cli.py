#!/usr/bin/env python
# -*- coding: utf-8 -

"""Console script for ecs_composex.sqs"""
import sys
import os
import argparse

from ecs_composex import DIR_DEST
from ecs_composex.common.aws import BUCKET_NAME
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.stacks import render_final_template
from ecs_composex.rds import create_rds_template


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
