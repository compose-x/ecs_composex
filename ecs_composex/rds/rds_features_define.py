# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to define and match RDS Features to other AWS resources.
"""

import re

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, AWS_PARTITION, GetAtt, Ref, Sub
from troposphere.iam import Policy as IamPolicy

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters, add_update_mapping
from ecs_composex.s3.s3_params import S3_BUCKET_ARN

S3_KEY = "x-s3"


def get_s3_bucket_arn_from_resource(db_stack, resource):
    param = resource.attributes_outputs[S3_BUCKET_ARN]["ImportParameter"]
    add_parameters(db_stack.stack_template, [param])
    if db_stack.parent_stack:
        add_parameters(db_stack.parent_stack.stack_template, [param])
        db_stack.parent_stack.Parameters.update(
            {
                param.title: GetAtt(
                    "s3",
                    f"Outputs.{resource.logical_name}{S3_BUCKET_ARN.title}",
                )
            }
        )
    db_stack.Parameters.update({param.title: Ref(param.title)})
    return Sub(f"${{{param.title}}}/*")


def set_from_x_s3(settings, db, db_stack, bucket_name):
    """
    Function to link the RDS DB to a Bucket defined in x-s3

    :param settings:
    :param db:
    :param str bucket_name:
    :return:
    """
    resource = None
    if not keyisset(S3_KEY, settings.compose_content):
        raise KeyError(
            f"No Buckets defined in the Compose file under {S3_KEY}.",
            settings.compose_content.keys(),
        )
    bucket_name = bucket_name.strip("x-s3::")
    buckets = settings.compose_content[S3_KEY]
    if bucket_name not in [res.name for res in buckets.values()]:
        LOG.error(
            f"No bucket {bucket_name} in x-s3. Buckets defined: {[res.name for res in buckets.values()]}"
        )
        return
    for resource in buckets.values():
        if bucket_name == resource.name:
            break
    if not resource:
        return
    if resource.cfn_resource:
        return get_s3_bucket_arn_from_resource(db_stack, resource)
    elif resource.lookup and keyisset("s3", settings.mappings):
        add_update_mapping(db_stack.stack_template, "s3", settings.mappings["s3"])
        return resource.lookup_properties[S3_BUCKET_ARN]


def import_bucket_from_arn(bucket):
    """
    Function to import a bucket defined by its ARN, supports to detect the path in bucket for objects

    :param str bucket:
    :return: the bucket ARN to use
    :rtype: str
    """
    bucket_arn_path_re = re.compile(
        r"(arn:aws:s3:::(?:[a-zA-Z0-9-.]+))(/path/to/files)?"
    )
    if not bucket_arn_path_re.match(bucket):
        raise ValueError(
            "The Bucket ARN provided is not valid. Expecting format",
            bucket_arn_path_re.pattern,
        )
    elif bucket_arn_path_re.match(bucket):
        bucket_arn = bucket
    else:
        bucket_arn = f"{bucket}/*"

    return bucket_arn


def import_raw_bucket_name(bucket) -> Sub:
    """
    Function to import and define a bucket ARN from bucket name alone and support for path to be defined
    :param str bucket:
    :return: the bucket ARN
    :rtype: Sub
    """
    bucket_name_path_re = re.compile(r"(?:[a-zA-Z0-9-.]+)(/path/to/files)?")
    bucket_arn = Ref(AWS_NO_VALUE)
    if not bucket_name_path_re.match(bucket):
        raise ValueError(
            "Bucket name and path are not valid. Expecting format",
            bucket_name_path_re.pattern,
        )
    if (
        bucket_name_path_re.match(bucket)
        and len(bucket_name_path_re.match(bucket).groups()) == 1
    ):
        bucket_arn = Sub(f"arn:${{{AWS_PARTITION}}}:s3:::{bucket}/*")
    elif (
        bucket_name_path_re.match(bucket)
        and len(bucket_name_path_re.match(bucket).groups()) == 2
    ):
        bucket_arn = Sub(f"arn:${{{AWS_PARTITION}}}:s3:::{bucket}")
    return bucket_arn


def define_s3_bucket_arns(settings, db, db_stack, config) -> list:
    """
    Function to define the IAM Policy for S3Import access

    :param settings:
    :param db:
    :param db_stack:
    :param config:
    :return:
    """
    bucket_arns = []
    for bucket in config:
        bucket_arn = None
        if not isinstance(bucket, str):
            raise TypeError(
                "All buckets defined in IamAccess/Buckets must be of type",
                str,
                "Got",
                type(bucket),
            )
        if bucket.startswith("x-s3"):
            bucket_arn = set_from_x_s3(settings, db, db_stack, bucket)
        elif bucket.startswith("arn:aws"):
            bucket_arn = import_bucket_from_arn(bucket)
        elif not bucket.startswith("arn:aws"):
            bucket_arn = import_raw_bucket_name(bucket)
        if bucket_arn:
            bucket_arns.append(bucket_arn)

    return bucket_arns


def define_s3_export_feature_policy(settings, db, db_stack, config) -> IamPolicy:
    """
    Function to define the IAM Policy for S3Import access

    :param settings:
    :param db:
    :param config:
    :return:
    """
    bucket_arns = define_s3_bucket_arns(settings, db, db_stack, config)
    policy = IamPolicy(
        PolicyName=f"S3AccessFor{db.logical_name}",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3WriteObjectsAccess",
                    "Effect": "Allow",
                    "Action": ["s3:PutObject*"],
                    "Resource": bucket_arns,
                }
            ],
        },
    )
    return policy


def define_s3_import_feature_policy(settings, db, db_stack, config) -> IamPolicy:
    """
    Function to define the IAM Policy for S3Import access

    :param settings:
    :param db:
    :param db_stack:
    :param config:
    :return:
    """
    bucket_arns = define_s3_bucket_arns(settings, db, db_stack, config)
    policy = IamPolicy(
        PolicyName=f"S3AccessFor{db.logical_name}",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3ReadObjectsAccess",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject*"],
                    "Resource": bucket_arns,
                }
            ],
        },
    )
    return policy
