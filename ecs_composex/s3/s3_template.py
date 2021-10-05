#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    Ref,
    Sub,
    s3,
)

from ecs_composex.common import LOG
from ecs_composex.resource_settings import generate_resource_permissions
from ecs_composex.resources_import import import_record_properties
from ecs_composex.s3.s3_perms import ACCESS_TYPES


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


def implement_bucket_policy(bucket, param_key, bucket_template):
    """
    Function to parse the input parameter for the Bucket Policy, and generate the policy accordingly

    :param ecs_composex.s3.s3_stack.Bucket bucket:
    :param troposphere.Template bucket_template:
    """
    statement = []
    managed_policies = "PredefinedBucketPolicies"
    policy_document = {"Version": "2012-10-17", "Statement": statement}
    if keyisset(managed_policies, bucket.parameters[param_key]) and keyisset(
        managed_policies, ACCESS_TYPES
    ):
        unique_policies = list(
            set(bucket.parameters[param_key]["PredefinedBucketPolicies"])
        )
        for policy_name in unique_policies:
            if policy_name not in ACCESS_TYPES[managed_policies].keys():
                LOG.error(
                    f"Policy {policy_name} is not defined as part of possible permissions set"
                )
                continue
            policies = generate_resource_permissions(
                bucket.logical_name,
                ACCESS_TYPES[managed_policies],
                Sub(f"arn:${{{AWS_PARTITION}}}:s3:::${{{bucket.cfn_resource.title}}}"),
            )
            statement += policies[policy_name].PolicyDocument["Statement"]
    bucket_policy = s3.BucketPolicy(
        f"{bucket.logical_name}BucketPolicy",
        Bucket=Ref(bucket.cfn_resource),
        PolicyDocument=policy_document,
        DependsOn=[bucket.cfn_resource.title],
    )
    bucket_template.add_resource(bucket_policy)


def evaluate_parameters(bucket, bucket_template):
    """

    :param ecs_composex.s3.s3_stack.Bucket bucket:
    :param troposphere.Template bucket_template:
    """
    if bucket.mappings or bucket.use:
        return
    if not bucket.parameters:
        return

    parameters = {"BucketPolicy": implement_bucket_policy}
    for name, function in parameters.items():
        if keyisset(name, bucket.parameters) and function:
            function(bucket, name, bucket_template)
