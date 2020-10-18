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

from troposphere import Ref, s3, AWS_NO_VALUE

from ecs_composex.common import keyisset
from ecs_composex.s3 import metadata


def create_bucket_encryption_default(props=None):
    if props is None:
        props = {"SSEAlgorithm": "AES256"}
    default_encryption = s3.ServerSideEncryptionByDefault(**props)
    return s3.BucketEncryption(
        ServerSideEncryptionConfiguration=[
            s3.ServerSideEncryptionRule(
                ServerSideEncryptionByDefault=default_encryption
            )
        ]
    )


def handle_bucket_encryption(properties, settings):
    """
    Function to handle the S3 bucket encryption.

    :param dict properties:
    :param dict settings:
    :return:
    """
    default = create_bucket_encryption_default()
    if not keyisset("BucketEncryption", properties) and not keyisset(
        "BucketEncryption", settings
    ):
        return default
    elif keyisset("BucketEncryption", settings):
        if (
            keyisset("SSEAlgorithm", settings["BucketEncryption"])
            and settings["BucketEncryption"]["SSEAlgorithm"] == "AES256"
        ):
            return default
        elif (
            keyisset("SSEAlgorithm", settings["BucketEncryption"])
            and settings["BucketEncryption"]["SSEAlgorithm"] == "aws:kms"
        ):
            if not keyisset("KMSMasterKeyID", settings["BucketEncryption"]):
                raise KeyError("Missing attribute KMSMasterKeyID for KMS Encryption")
            else:
                return create_bucket_encryption_default(settings["BucketEncryption"])


def define_public_block_access(properties):
    """
    Function to define the block access.
    :param properties:
    :return:
    """


def define_accelerate_config(properties, settings):
    """
    Function to define AccelerateConfiguration

    :param properties:
    :param settings:
    :return:
    """
    config = s3.AccelerateConfiguration(
        AccelerationStatus=s3.s3_transfer_acceleration_status("Suspended")
    )
    if keyisset("AccelerateConfiguration", properties):
        config = s3.AccelerateConfiguration(
            AccelerationStatus=s3.s3_transfer_acceleration_status("Suspended")
            if not keyisset("AccelerationStatus", properties["AccelerateConfiguration"])
            else s3.s3_transfer_acceleration_status(
                properties["AccelerateConfiguration"]["AccelerationStatus"]
            )
        )
    elif keyisset("AccelerationStatus", settings):
        config = s3.AccelerateConfiguration(
            AccelerationStatus=settings["AccelerationStatus"]
        )
    return config


def define_bucket(bucket):
    """
    Function to generate the S3 bucket object

    :param ecs_composex.s3.s3_stack.Bucket bucket:
    :param definition:
    :return:
    """
    props = {
        "AccelerateConfiguration": define_accelerate_config(
            bucket.properties, bucket.settings
        ),
        "AccessControl": s3.BucketOwnerFullControl
        if not keyisset("AccessControl", bucket.properties)
        else bucket.properties["AccessControl"],
        "BucketEncryption": handle_bucket_encryption(
            bucket.properties, bucket.settings
        ),
        "BucketName": bucket.properties["BucketName"]
        if keyisset("BucketName", bucket.properties)
        else Ref(AWS_NO_VALUE),
        "ObjectLockEnabled": False
        if not keyisset("ObjectLockEnabled", bucket.properties)
        else bucket.properties["ObjectLockEnabled"],
        "PublicAccessBlockConfiguration": s3.PublicAccessBlockConfiguration(
            **bucket.properties["PublicAccessBlockConfiguration"]
        )
        if keyisset("PublicAccessBlockConfiguration", bucket.properties)
        else s3.PublicAccessBlockConfiguration(
            BlockPublicAcls=True,
            BlockPublicPolicy=True,
            IgnorePublicAcls=True,
            RestrictPublicBuckets=True,
        ),
        "VersioningConfiguration": s3.VersioningConfiguration(
            Status=bucket.properties["VersioningConfiguration"]["Status"]
        )
        if keyisset("VersioningConfiguration", bucket.properties)
        else Ref(AWS_NO_VALUE),
        "Metadata": metadata,
    }
    bucket = s3.Bucket(bucket.logical_name, **props)
    return bucket


def generate_bucket(bucket, settings):
    """
    Function to identify whether create new bucket or lookup for existing bucket

    :param ecs_composex.s3.s3_stack.Bucket bucket:
    :param settings:
    :return:
    """
    bucket = define_bucket(bucket)
    return bucket
