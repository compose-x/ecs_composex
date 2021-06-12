#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

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
