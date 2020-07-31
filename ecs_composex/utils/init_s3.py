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

from botocore.exceptions import ClientError
from ecs_composex.common import LOG


def create_bucket(bucket_name, session):
    """
    Function that checks if the S3 bucket exists and if not attempts to create it.

    :param bucket_name: name of the s3 bucket
    :type bucket_name: str
    :param session: boto3 session to use if wanted to override settings.
    :type session: boto3.session.Session
    :returns: True/False, Returns whether the bucket exists or not for upload
    :rtype: bool
    """
    client = session.client("s3")
    region = session.region_name
    location = {"LocationConstraint": region}
    try:
        client.create_bucket(
            ACL="private",
            Bucket=bucket_name,
            ObjectLockEnabledForBucket=True,
            CreateBucketConfiguration=location,
        )
        LOG.info(f"Bucket {bucket_name} successfully created.")
    except client.exceptions.BucketAlreadyExists:
        LOG.warning(f"Bucket {bucket_name} already exists.")
    except client.exceptions.BucketAlreadyOwnedByYou:
        LOG.info(f"You already own the bucket {bucket_name}")
    except ClientError as error:
        LOG.error("Error whilst creating the bucket")
        LOG.error(error)
        raise
