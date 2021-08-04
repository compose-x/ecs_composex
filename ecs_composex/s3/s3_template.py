#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_NO_VALUE, AWS_REGION, Ref, Sub, s3

from ecs_composex.common import LOG
from ecs_composex.resources_import import import_record_properties


def define_bucket_name(bucket):
    """
    Function to automatically add Region and Account ID to the bucket name.
    If set, will use a user-defined separator, else, `-`

    :param bucket:
    :return: The bucket name
    :rtype: str
    """
    separator = (
        bucket.settings["NameSeparator"]
        if keyisset("NameSeparator", bucket.parameters)
        and isinstance(bucket.parameters["NameSeparator"], str)
        else r"-"
    )
    expand_region_key = "ExpandRegionToBucket"
    expand_account_id = "ExpandAccountIdToBucket"
    base_name = (
        None
        if not keyisset("BucketName", bucket.properties)
        else bucket.properties["BucketName"]
    )
    if base_name:
        if keyisset(expand_region_key, bucket.parameters) and keyisset(
            expand_account_id, bucket.parameters
        ):
            return f"{base_name}{separator}${{{AWS_ACCOUNT_ID}}}{separator}${{{AWS_REGION}}}"
        elif keyisset(expand_region_key, bucket.parameters) and not keyisset(
            expand_account_id, bucket.parameters
        ):
            return f"{base_name}{separator}${{{AWS_REGION}}}"
        elif not keyisset(expand_region_key, bucket.parameters) and keyisset(
            expand_account_id, bucket.parameters
        ):
            return f"{base_name}{separator}${{{AWS_ACCOUNT_ID}}}"
        elif not keyisset(expand_account_id, bucket.parameters) and not keyisset(
            expand_region_key, bucket.parameters
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
    bucket_name = define_bucket_name(bucket)
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
