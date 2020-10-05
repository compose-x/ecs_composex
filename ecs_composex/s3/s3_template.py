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

from troposphere import s3
from troposphere import Ref, GetAtt, Sub
from troposphere import AWS_NO_VALUE

from ecs_composex.common import LOG, keyisset
from ecs_composex.s3 import metadata
from ecs_composex.s3.s3_params import S3_BUCKET_NAME


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


def define_bucket(bucket_name, res_name, definition):
    """
    Function to generate the S3 bucket object

    :param bucket_name:
    :param res_name:
    :param definition:
    :return:
    """
    properties = definition["Properties"] if keyisset("Properties", definition) else {}
    settings = definition["Settings"] if keyisset("Settings", definition) else {}
    props = {
        "AccelerateConfiguration": define_accelerate_config(properties, settings),
        "AccessControl": s3.BucketOwnerFullControl
        if not keyisset("AccessControl", properties)
        else properties["AccessControl"],
        "BucketEncryption": handle_bucket_encryption(definition, settings),
        "BucketName": definition["BucketName"]
        if keyisset("BucketName", definition)
        else Ref(AWS_NO_VALUE),
        "ObjectLockEnabled": False
        if not keyisset("ObjectLockEnabled", properties)
        else properties["ObjectLockEnabled"],
        "PublicAccessBlockConfiguration": s3.PublicAccessBlockConfiguration(
            **properties["PublicAccessBlockConfiguration"]
        )
        if keyisset("PublicAccessBlockConfiguration", properties)
        else s3.PublicAccessBlockConfiguration(
            BlockPublicAcls=True,
            BlockPublicPolicy=True,
            IgnorePublicAcls=True,
            RestrictPublicBuckets=True,
        ),
        "VersioningConfiguration": s3.VersioningConfiguration(
            Status=properties["VersioningConfiguration"]["Status"]
        )
        if keyisset("VersioningConfiguration", properties)
        else Ref(AWS_NO_VALUE),
        "Metadata": metadata,
    }
    bucket = s3.Bucket(res_name, **props)
    return bucket


def generate_bucket(bucket_name, bucket_res_name, bucket_definition, settings):
    """
    Function to identify whether create new bucket or lookup for existing bucket

    :param bucket_name:
    :param bucket_res_name:
    :param bucket_definition:
    :param settings:
    :return:
    """
    if keyisset("Lookup", bucket_definition):
        LOG.info("If bucket is found, its ARN will be added to the task")
        return
    elif keyisset("Use", bucket_definition):
        LOG.info(f"Assuming bucket {bucket_name} exists to use.")
        return
    if not keyisset("Properties", bucket_definition):
        LOG.warning(f"Properties for bucket {bucket_name} were not defined. Skipping")
        return
    bucket = define_bucket(bucket_name, bucket_res_name, bucket_definition)
    return bucket
