#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to pass permissions to Services to access S3 buckets.
"""
import re

from compose_x_common.aws.kms import (
    KMS_ALIAS_ARN_RE,
    KMS_KEY_ARN_RE,
    get_key_from_alias,
)
from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap, Ref, Sub

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.aws import define_lookup_role_from_info
from ecs_composex.common.compose_resources import get_parameter_settings
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.kms.kms_params import MOD_KEY as KMS_MOD
from ecs_composex.resource_settings import (
    add_iam_policy_to_service_task_role,
    generate_resource_permissions,
    get_selected_services,
)
from ecs_composex.s3.s3_params import MOD_KEY as S3_MOD
from ecs_composex.s3.s3_params import (
    RES_KEY,
    S3_BUCKET_ARN,
    S3_BUCKET_KMS_KEY,
    S3_BUCKET_NAME,
)

ACCESS_TYPES = get_access_types(S3_MOD)


def assign_service_permissions_to_bucket(bucket, family, services, access, value, arn):
    bucket_key = "bucket"
    objects_key = "objects"
    ssl_key = "enforceSecureConnection"

    bucket.generate_resource_envvars()
    if keyisset(bucket_key, access):
        bucket_perms = generate_resource_permissions(
            f"BucketAccess{bucket.logical_name}",
            ACCESS_TYPES[bucket_key],
            arn=arn,
        )
        add_iam_policy_to_service_task_role(
            family, bucket, bucket_perms, access[bucket_key], services
        )
    if keyisset(objects_key, access):
        objects_perms = generate_resource_permissions(
            f"ObjectsAccess{bucket.logical_name}",
            ACCESS_TYPES[objects_key],
            arn=Sub("${BucketArn}/*", BucketArn=arn),
        )
        add_iam_policy_to_service_task_role(
            family,
            bucket,
            objects_perms,
            access[objects_key],
            services,
        )
    if keyisset(ssl_key, access):
        ssl_perms = generate_resource_permissions(
            f"SslBucketObjefsAccess{bucket.logical_name}",
            ACCESS_TYPES[ssl_key],
            arn=arn,
        )
        add_iam_policy_to_service_task_role(
            family,
            bucket,
            ssl_perms,
            ssl_key,
            services,
        )


def assign_new_bucket_to_services(bucket, res_root_stack, nested=False):
    """
    Function to assign the bucket services permissions to access the s3 bucket.
    :param ecs_composex.s3.s3_stack.Bucket bucket:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param bool nested:
    :return:
    """
    bucket_key = "bucket"
    objects_key = "objects"
    ssl_key = "enforceSecureConnection"
    attributes_settings = [
        get_parameter_settings(bucket, attribute)
        for attribute in bucket.output_properties
    ]
    params_to_add = []
    params_values = {}
    for setting in attributes_settings:
        params_to_add.append(setting[1])
        params_values[setting[0]] = setting[2]
    for target in bucket.families_targets:
        select_services = get_selected_services(bucket, target)
        access = {objects_key: "RW", bucket_key: "ListOnly", ssl_key: False}
        if select_services:
            access = target[3]
            add_parameters(
                target[0].template,
                params_to_add,
            )
            target[0].stack.Parameters.update(params_values)
            assign_service_permissions_to_bucket(
                bucket,
                target[0],
                select_services,
                access,
                value=Ref(bucket.attributes_outputs[S3_BUCKET_NAME]["ImportParameter"]),
                arn=Ref(bucket.attributes_outputs[S3_BUCKET_ARN]["ImportParameter"]),
            )
            if res_root_stack.title not in target[0].stack.DependsOn:
                target[0].stack.DependsOn.append(res_root_stack.title)


def handle_new_resources(
    resource,
    services_stack,
    res_root_stack,
    nested=False,
):
    """

    :param resource: The resource
    :type resource: ecs_composex.s3.s3_stack.Bucket
    :param services_stack:
    :param res_root_stack:
    :param nested:
    :return:
    """
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_resources(
                resource,
                services_stack,
                s_resources[resource_name],
                nested=True,
            )
    assign_new_bucket_to_services(resource, res_root_stack, nested)


def define_lookup_buckets_access(bucket, target, services):
    """
    Function to create the IAM policy for the service access to bucket

    :param bucket:
    :param target:
    :param services:
    :return:
    """
    bucket_key = "bucket"
    objects_key = "objects"
    ssl_key = "enforceSecureConnection"
    access = {objects_key: "RW", bucket_key: "ListOnly", ssl_key: False}
    if isinstance(target[3], str):
        LOG.warning(
            "For s3 buckets, you should define a dict for access, with bucket and/or object policies separate."
            " Using default RW Objects and ListBucket"
        )
    elif isinstance(target[3], dict) and (
        keyisset(objects_key, target[3]) or keyisset(bucket_key, target[3])
    ):
        access = target[3]
    elif isinstance(target[3], dict) and (
        not keyisset(objects_key, target[3]) or not keyisset(bucket_key, target[3])
    ):
        raise KeyError("You must define at least bucket or object access")
    bucket.generate_resource_envvars()
    if keyisset(bucket_key, access):
        bucket_perms = generate_resource_permissions(
            f"BucketAccess{bucket.logical_name}",
            ACCESS_TYPES[bucket_key],
            arn=FindInMap("s3", bucket.logical_name, "Arn"),
        )
        add_iam_policy_to_service_task_role(
            target[0],
            bucket,
            bucket_perms,
            access[bucket_key],
            services,
        )
    if keyisset(objects_key, access):
        objects_perms = generate_resource_permissions(
            f"ObjectsAccess{bucket.logical_name}",
            ACCESS_TYPES[objects_key],
            arn=Sub(
                "${BucketArn}/*",
                BucketArn=FindInMap("s3", bucket.logical_name, "Arn"),
            ),
        )
        add_iam_policy_to_service_task_role(
            target[0],
            bucket,
            objects_perms,
            access[objects_key],
            services,
        )
    if keyisset(ssl_key, access):
        ssl_perms = generate_resource_permissions(
            f"SslBucketObjefsAccess{bucket.logical_name}",
            ACCESS_TYPES[ssl_key],
            arn=FindInMap("s3", bucket.logical_name, "Arn"),
        )
        add_iam_policy_to_service_task_role(
            target[0],
            bucket,
            ssl_perms,
            ssl_key,
            services,
        )


def assign_lookup_buckets(bucket, mappings):
    """
    Function to add the lookup bucket to service access

    :param ecs_composex.s3.s3_stacks.Bucket bucket:
    :param dict mappings:
    """
    if not keyisset(bucket.logical_name, mappings):
        LOG.warning(f"Bucket {bucket.logical_name} was not found in mappings. Skipping")
        return
    bucket.init_outputs()
    bucket.generate_outputs()
    bucket.generate_resource_envvars()
    for target in bucket.families_targets:
        select_services = get_selected_services(bucket, target)
        if select_services:
            target[0].template.add_mapping("s3", mappings)
            if keyisset(S3_BUCKET_KMS_KEY.return_value, mappings[bucket.logical_name]):
                kms_perms = generate_resource_permissions(
                    f"{bucket.logical_name}KmsKey",
                    get_access_types(KMS_MOD),
                    arn=FindInMap(
                        "s3", bucket.logical_name, S3_BUCKET_KMS_KEY.return_value
                    ),
                )
                add_iam_policy_to_service_task_role(
                    target[0],
                    bucket,
                    kms_perms,
                    "EncryptDecrypt",
                    select_services,
                )
            define_lookup_buckets_access(bucket, target, select_services)


def s3_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to handle permissions assignment to ECS services.

    :param resources: x-sqs queues defined in compose file
    :param ecs_composex.common.stack.ComposeXStack services_stack: services root stack
    :param ecs_composex.common.stack.ComposeXStack res_root_stack: s3 root stack
    :param ecs_composex.common.settings.ComposeXSettings settings: ComposeX Settings for execution
    :return:
    """
    if hasattr(res_root_stack, "is_void") and not res_root_stack.is_void:
        new_resources = [
            resources[res_name]
            for res_name in resources
            if resources[res_name].cfn_resource
        ]
        for res in new_resources:
            LOG.info(f"Creating {res.name} as {res.logical_name}")
            handle_new_resources(
                res,
                services_stack,
                res_root_stack,
            )
    lookup_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].mappings and resources[res_name].lookup
    ]
    use_resources = [
        resources[name]
        for name in resources
        if resources[name].use and resources[name].mappings
    ]
    for res in lookup_resources:
        assign_lookup_buckets(res, settings.mappings[RES_KEY])
    for res in use_resources:
        assign_lookup_buckets(res, settings.mappings[RES_KEY])
