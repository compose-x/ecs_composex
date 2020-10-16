#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Functions to find buckets and identify settings about these.
"""

import re

from botocore.exceptions import ClientError

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.aws import define_tagsgroups_filter_tags
from ecs_composex.s3.s3_params import S3_ARN_REGEX
from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api


# def return_db_config(bucket_arn, session):
#     """
#
#     :param str bucket_arn:
#     :param boto3.session.Session session:
#     :return:
#     """
#     client = session.client("s3")
#     try:
#         client.head_bucket(Bucket=bucket_name)
#             return bucket_name
#         except client.exceptions.NoSuchBucket:
#             return None
#         except ClientError as error:
#             LOG.error(error)
#             raise


def lookup_bucket(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    rds_types = {
        "s3": {"regexp": r"(?:^arn:aws(?:-[a-z]+)?:s3:::)([\S]+)$"},
    }
    res_type = None
    if keyisset("bucket", lookup):
        res_type = "bucket"
    bucket_arn = find_aws_resource_arn_from_tags_api(
        lookup[res_type],
        session,
        "rds",
        res_type,
        types=rds_types,
        service_is_type=True,
    )
    print(bucket_arn)
    if not bucket_arn:
        return None
    # bucket_config = return_db_config(bucket_arn, session)
    # LOG.debug(bucket_config)
    # return bucket_config
