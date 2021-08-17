#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from boto3.session import Session
from botocore.exceptions import ClientError

from ecs_composex.common import LOG


def create_bucket(bucket_name, session, no_location=False):
    """
    Function that checks if the S3 bucket exists and if not attempts to create it.

    :param bucket_name: name of the s3 bucket
    :type bucket_name: str
    :param session: boto3 session to use if wanted to override settings.
    :type session: boto3.session.Session
    :param no_location: Disable location constraint
    :returns: True/False, Returns whether the bucket exists or not for upload
    :rtype: bool
    """
    s3_session = Session()
    client = s3_session.resource("s3")
    bucket = client.Bucket(bucket_name)
    params = {
        "ACL": "private",
        "Bucket": bucket_name,
        "ObjectLockEnabledForBucket": True,
        "CreateBucketConfiguration": {"LocationConstraint": s3_session.region_name},
    }
    if no_location or s3_session.region_name == "us-east-1":
        del params["CreateBucketConfiguration"]
    try:
        bucket.create(**params)
        LOG.info(f"Bucket {bucket_name} successfully created.")
    except client.meta.client.exceptions.BucketAlreadyExists:
        LOG.warning(f"Bucket {bucket_name} already exists.")
    except client.meta.client.exceptions.BucketAlreadyOwnedByYou:
        LOG.info(f"You already own the bucket {bucket_name}")
    except ClientError as error:
        print(error.response)
        if error.response["Error"]["Code"] == "InvalidLocationConstraint":
            create_bucket(bucket_name, session, True)
        else:
            LOG.error("Error whilst creating the bucket")
            LOG.error(error)
            raise
