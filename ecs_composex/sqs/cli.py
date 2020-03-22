#!/usr/bin/env python
# -*- coding: utf-8 -

"""Console script for ecs_composex.sqs"""
import sys
import argparse

from ecs_composex.common.aws import BUCKET_NAME
from ecs_composex.sqs import create_sqs_template


def main():
    """Console script for ecs_composex."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-b', '--bucket-name', type=str, required=False, default=BUCKET_NAME,
        help='Bucket name to upload the templates to', dest='BucketName'
    )
    parser.add_argument(
        '-f', '--compose-file', required=True, dest="ComposeXFile",
        help="Path to the Docker Compose / ComposeX file"
    )
    parser.add_argument(
        '-o', '--output-file', required=True,
        help="Output file for the template body"
    )
    parser.add_argument('_', nargs='*')
    args = parser.parse_args()

    template = create_sqs_template(**vars(args))
    with open(args.output_file, 'w') as tpl_fd:
        if args.output_file.endswith('.yml') or args.output_file.endswith('.yaml'):
            tpl_fd.write(template.to_yaml())
        else:
            tpl_fd.write(template.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
