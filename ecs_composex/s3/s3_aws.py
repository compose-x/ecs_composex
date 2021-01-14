#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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
from ecs_composex.common.aws import (
    find_aws_resource_arn_from_tags_api,
    define_lookup_role_from_info,
)


def return_bucket_config(bucket_arn, session):
    """

    :param str bucket_arn:
    :param boto3.session.Session session:
    :return:
    """
    bucket_name_finder = re.compile(r"([a-zA-Z0-9.\-_]{1,255}$)")
    bucket_name = bucket_name_finder.findall(bucket_arn)[-1]
    bucket_config = {"Name": bucket_name, "Arn": bucket_arn}
    client = session.client("s3")
    try:
        client.head_bucket(Bucket=bucket_name)
        try:
            encryption_config_r = client.get_bucket_encryption(Bucket=bucket_name)
            if keyisset("ServerSideEncryptionConfiguration", encryption_config_r):
                bucket_config.update(
                    {
                        "ServerSideEncryptionConfiguration": encryption_config_r[
                            "ServerSideEncryptionConfiguration"
                        ]
                    }
                )
        except ClientError as error:
            if (
                not error.response["Error"]["Code"]
                == "ServerSideEncryptionConfigurationNotFoundError"
            ):
                raise
            LOG.warning(error.response["Error"]["Message"])
        return bucket_config
    except client.exceptions.NoSuchBucket:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_bucket_config(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    s3_types = {
        "s3": {"regexp": r"(?:^arn:aws(?:-[a-z]+)?:s3:::)([\S]+)$"},
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    bucket_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "s3",
        types=s3_types,
    )
    if not bucket_arn:
        return None
    config = return_bucket_config(bucket_arn, lookup_session)
    LOG.debug(config)
    return config
