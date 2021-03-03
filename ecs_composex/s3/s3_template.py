#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@compose-x.io>
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

from ecs_composex.common import keyisset, LOG
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
