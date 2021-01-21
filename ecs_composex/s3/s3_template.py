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

from troposphere import Ref, Sub, s3, AWS_NO_VALUE, AWS_ACCOUNT_ID, AWS_REGION

from ecs_composex.common import keyisset, keypresent, LOG
from ecs_composex.resources_import import import_record_properties


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


def handle_encryption_settings(setting):
    """
    Function to parse the macro-like settings for bucket creation

    :param bool,str setting:
    :return:
    """
    if (
        isinstance(setting, bool)
        and setting is True
        or isinstance(setting, str)
        and setting == "AES256"
    ):
        return create_bucket_encryption_default()


def handle_encryption_rule(encryption_rules):
    """
    Function to handle the Encryption rule for BucketEncryption

    :param list encryption_rules:
    :return:
    """
    if len(encryption_rules) != 1:
        raise ValueError("There can only be one encryption rule")
    prop_key = "ServerSideEncryptionByDefault"
    rule = encryption_rules[0]
    if keyisset("ServerSideEncryptionByDefault", rule):
        if (
            keyisset("SSEAlgorithm", rule[prop_key])
            and rule[prop_key]["SSEAlgorithm"] == "AES256"
        ):
            return create_bucket_encryption_default()
        elif (
            keyisset("SSEAlgorithm", rule[prop_key])
            and rule[prop_key]["SSEAlgorithm"] == "aws:kms"
        ):
            if not keyisset("KMSMasterKeyID", rule[prop_key]):
                raise KeyError("Missing attribute KMSMasterKeyID for KMS Encryption")
            else:
                return create_bucket_encryption_default(rule[prop_key])


def handle_bucket_encryption(properties, settings):
    """
    Function to handle the S3 bucket encryption.

    :param dict properties:
    :param dict settings:
    :return:
    """
    settings_key = "EnableEncryption"
    default = create_bucket_encryption_default()
    if not keyisset("BucketEncryption", properties) and not keyisset(
        settings_key, settings
    ):
        return default
    elif keyisset(settings_key, settings):
        return handle_encryption_settings(settings[settings_key])
    elif (
        keyisset("BucketEncryption", properties)
        and keyisset(
            "ServerSideEncryptionConfiguration", properties["BucketEncryption"]
        )
        and properties["BucketEncryption"]["ServerSideEncryptionConfiguration"]
    ):
        handle_encryption_rule(
            properties["BucketEncryption"]["ServerSideEncryptionConfiguration"]
        )
    return create_bucket_encryption_default()


def define_public_block_access(properties):
    """
    Function to define the block access.
    :param properties:
    :return:
    """
    if keyisset("PublicAccessBlockConfiguration", properties):
        return s3.PublicAccessBlockConfiguration(
            **properties["PublicAccessBlockConfiguration"]
        )

    else:
        return s3.PublicAccessBlockConfiguration(
            BlockPublicAcls=True,
            BlockPublicPolicy=True,
            IgnorePublicAcls=True,
            RestrictPublicBuckets=True,
        )


def define_objects_locking(properties):
    """
    Function to define bucket objects lock

    :param dict properties:
    :return:
    """
    if not keypresent("ObjectLockEnabled", properties):
        return False
    else:
        return properties["ObjectLockEnabled"]


def define_bucket_versioning(properties):
    """
    Function to define bucket versioning

    :param dict properties:
    :return:
    """
    if keyisset("VersioningConfiguration", properties):
        return s3.VersioningConfiguration(
            Status=properties["VersioningConfiguration"]["Status"]
        )

    else:
        return Ref(AWS_NO_VALUE)


def define_access_control(properties):
    if not keyisset("AccessControl", properties):
        return s3.BucketOwnerFullControl
    else:
        return properties["AccessControl"]


def define_accelerate_config(properties, settings, bucket_name):
    """
    Function to define AccelerateConfiguration

    :param properties:
    :param settings:
    :param bucket_name: The name of the bucket.
    :return:
    """
    config = Ref(AWS_NO_VALUE)
    if (
        isinstance(bucket_name, str)
        and bucket_name.find(".") >= 0
        or keyisset("BucketName", properties)
        and properties["BucketName"].find(".") > 0
    ):
        LOG.warning(
            "Your bucket name contains a `.` which is incompatible with Acceleration"
        )
        return Ref(AWS_NO_VALUE)
    if keyisset("AccelerateConfiguration", properties):
        config = s3.AccelerateConfiguration(
            AccelerationStatus=s3.s3_transfer_acceleration_status("Suspended")
            if not keyisset("AccelerationStatus", properties["AccelerateConfiguration"])
            else s3.s3_transfer_acceleration_status(
                properties["AccelerateConfiguration"]["AccelerationStatus"]
            )
        )
    elif keyisset("EnableAcceleration", settings) and isinstance(
        settings["EnableAcceleration"], bool
    ):
        config = s3.AccelerateConfiguration(AccelerationStatus="Enabled")
    return config


def define_bucket_name(properties, settings):
    """
    Function to automatically add Region and Account ID to the bucket name.
    If set, will use a user-defined separator, else, `-`

    :param dict properties:
    :param dict settings:
    :return: The bucket name
    :rtype: str
    """
    separator = (
        settings["NameSeparator"]
        if keyisset("NameSeparator", settings)
        and isinstance(settings["NameSeparator"], str)
        else r"-"
    )
    expand_region_key = "ExpandRegionToBucket"
    expand_account_id = "ExpandAccountIdToBucket"
    base_name = (
        None if not keyisset("BucketName", properties) else properties["BucketName"]
    )
    if base_name:
        if keyisset(expand_region_key, settings) and keyisset(
            expand_account_id, settings
        ):
            return f"{base_name}{separator}${{{AWS_ACCOUNT_ID}}}{separator}${{{AWS_REGION}}}"
        elif keyisset(expand_region_key, settings) and not keyisset(
            expand_account_id, settings
        ):
            return f"{base_name}{separator}${{{AWS_REGION}}}"
        elif not keyisset(expand_region_key, settings) and keyisset(
            expand_account_id, settings
        ):
            return f"{base_name}{separator}${{{AWS_ACCOUNT_ID}}}"
        elif not keyisset(expand_account_id, settings) and not keyisset(
            expand_region_key, settings
        ):
            LOG.warning(
                f"{base_name} - You defined the bucket without any extension. "
                "Bucket names must be unique. Make sure it is not already in-use"
            )
        return base_name
    return Ref(AWS_NO_VALUE)


def generate_bucket(bucket):
    """
    Function to generate the S3 bucket object

    :param ecs_composex.s3.s3_stack.Bucket bucket:
    :return:
    """
    bucket_name = define_bucket_name(bucket.properties, bucket.settings)
    final_bucket_name = (
        Sub(bucket_name)
        if isinstance(bucket_name, str)
        and (bucket_name.find(AWS_REGION) >= 0 or bucket_name.find(AWS_ACCOUNT_ID) >= 0)
        else bucket_name
    )
    LOG.debug(bucket_name)
    LOG.debug(final_bucket_name)
    props = import_record_properties(bucket.properties, s3.Bucket)
    props["BucketName"] = final_bucket_name
    bucket.cfn_resource = s3.Bucket(bucket.logical_name, **props)
    return bucket
