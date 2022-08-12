# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.s3.s3_bucket import Bucket
    from troposphere import NoValue
    from troposphere import Template

from compose_x_common.compose_x_common import keyisset
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    MAX_OUTPUTS,
    Ref,
    Sub,
    s3,
)

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import add_outputs, build_template
from ecs_composex.resource_settings import generate_resource_permissions
from ecs_composex.resources_import import import_record_properties

COMPOSEX_MAX_OUTPUTS = MAX_OUTPUTS - 10


def define_bucket_name(bucket: Bucket) -> str | NoValue:
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


def generate_bucket(bucket: Bucket) -> None:
    """
    Function to generate the S3 bucket object

    :param ecs_composex.s3.s3_bucket.Bucket bucket:
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


def handle_predefined_policies(
    bucket: Bucket, param_key: str, managed_policies_key: str, statement: list
) -> None:
    """
    Function to configure and add statements for bucket policy based on predefined Bucket Policies

    :param bucket:
    :param str param_key:
    :param str managed_policies_key:
    :param list statement:
    """
    unique_policies = list(
        set(bucket.parameters[param_key]["PredefinedBucketPolicies"])
    )
    for policy_name in unique_policies:
        if policy_name not in bucket.module.iam_policies[managed_policies_key].keys():
            LOG.error(
                f"Policy {policy_name} is not defined as part of possible permissions set"
            )
            continue
        policies = generate_resource_permissions(
            bucket.logical_name,
            bucket.module.iam_policies[managed_policies_key],
            Sub(f"arn:${{{AWS_PARTITION}}}:s3:::${{{bucket.cfn_resource.title}}}"),
        )
        statement += policies[policy_name].PolicyDocument["Statement"]


def handle_user_defined_policies(
    bucket: Bucket, param_key: str, user_policies_key: str, statement: list
):
    """
    Function to add user defined policies

    :param bucket:
    :param str param_key:
    :param str user_policies_key:
    :param list statement:
    """
    policies = bucket.parameters[param_key][user_policies_key]
    policy_docs = {}
    for count, policy_doc in enumerate(policies):
        if keyisset("Sid", policy_doc):
            name = policy_doc["Sid"]
        else:
            name = f"UserDefined{count}"
        policy_docs[name] = policy_doc
    generated_policies = generate_resource_permissions(
        bucket.logical_name,
        policy_docs,
        Sub(f"arn:${{{AWS_PARTITION}}}:s3:::${{{bucket.cfn_resource.title}}}"),
        True,
    )
    for policy in generated_policies.values():
        statement += policy.PolicyDocument["Statement"]


def implement_bucket_policy(bucket: Bucket, param_key: str, bucket_template: Template):
    """
    Function to parse the input parameter for the Bucket Policy, and generate the policy accordingly
    """
    statement = []
    managed_policies_key = "PredefinedBucketPolicies"
    user_policies_key = "Policies"
    policy_document = {"Version": "2012-10-17", "Statement": statement}
    if keyisset(managed_policies_key, bucket.parameters[param_key]) and keyisset(
        managed_policies_key, bucket.module.iam_policies
    ):
        handle_predefined_policies(bucket, param_key, managed_policies_key, statement)
    if keyisset(user_policies_key, bucket.parameters[param_key]):
        handle_user_defined_policies(bucket, param_key, user_policies_key, statement)
    bucket_policy = s3.BucketPolicy(
        f"{bucket.logical_name}BucketPolicy",
        Bucket=Ref(bucket.cfn_resource),
        PolicyDocument=policy_document,
        DependsOn=[bucket.cfn_resource.title],
    )
    bucket_template.add_resource(bucket_policy)


def evaluate_parameters(bucket, bucket_template):
    """
    Review bucket parameters to configure the bucket and extra properties.
    """
    if bucket.mappings:
        return
    if not bucket.parameters:
        return

    parameters = {"BucketPolicy": implement_bucket_policy}
    for name, function in parameters.items():
        if keyisset(name, bucket.parameters) and function:
            function(bucket, name, bucket_template)


def create_s3_template(new_buckets: list[Bucket], template: Template) -> Template:
    """
    Function to create the root S3 template.
    """
    mono_template = False
    if len(list(new_buckets)) <= COMPOSEX_MAX_OUTPUTS:
        mono_template = True

    for bucket in new_buckets:
        generate_bucket(bucket)
        if bucket.cfn_resource:
            bucket.init_outputs()
            bucket.generate_outputs()
            bucket_template = template
            if mono_template:
                bucket_template.add_resource(bucket.cfn_resource)
                add_outputs(bucket_template, bucket.outputs)
            elif not mono_template:
                bucket_template = build_template(
                    f"Template for S3 Bucket {bucket.name}"
                )
                bucket_template.add_resource(bucket.cfn_resource)
                add_outputs(bucket_template, bucket.outputs)
                bucket_stack = ComposeXStack(
                    bucket.logical_name, stack_template=bucket_template
                )
                template.add_resource(bucket_stack)
            evaluate_parameters(bucket, bucket_template)
    return template
