#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to pass permissions to Services to access S3 buckets.
"""
import re
from json import dumps

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_PARTITION, FindInMap, Ref, Sub

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.compose_resources import get_parameter_settings
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kms.kms_perms import ACCESS_TYPES as KMS_ACCESS_TYPES
from ecs_composex.resource_settings import (
    add_iam_policy_to_service_task_role,
    generate_resource_permissions,
    get_selected_services,
)
from ecs_composex.s3.s3_aws import lookup_bucket_config
from ecs_composex.s3.s3_params import MOD_KEY, S3_BUCKET_ARN, S3_BUCKET_NAME
from ecs_composex.s3.s3_perms import ACCESS_TYPES


def assign_service_permissions_to_bucket(bucket, family, services, access, value, arn):
    bucket_key = "bucket"
    objects_key = "objects"

    bucket.generate_resource_envvars()
    if keyisset(bucket_key, access):
        bucket_perms = generate_resource_permissions(
            f"BucketAccess{bucket.logical_name}",
            ACCESS_TYPES[bucket_key],
            arn=arn,
        )
        add_iam_policy_to_service_task_role(
            family.template, bucket, bucket_perms, access[bucket_key], services
        )
    if keyisset(objects_key, access):
        objects_perms = generate_resource_permissions(
            f"ObjectsAccess{bucket.logical_name}",
            ACCESS_TYPES[objects_key],
            arn=Sub("${BucketArn}/*", BucketArn=arn),
        )
        add_iam_policy_to_service_task_role(
            family.template,
            bucket,
            objects_perms,
            access[objects_key],
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
        access = {objects_key: "RW", bucket_key: "ListOnly"}
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


def get_bucket_kms_key_from_config(bucket_config):
    """
    Functiont to get the KMS Encryption key if defined.

    :param bucket_config:
    :return:
    """
    rules = (
        []
        if not (
            keyisset("ServerSideEncryptionConfiguration", bucket_config)
            and keyisset("Rules", bucket_config["ServerSideEncryptionConfiguration"])
        )
        else bucket_config["ServerSideEncryptionConfiguration"]["Rules"]
    )
    for rule in rules:
        if keyisset("ApplyServerSideEncryptionByDefault", rule):
            settings = rule["ApplyServerSideEncryptionByDefault"]
            if (
                keyisset("SSEAlgorithm", settings)
                and settings["SSEAlgorithm"] == "aws:kms"
                and keyisset("KMSMasterKeyID", settings)
            ):
                return settings["KMSMasterKeyID"]
    return None


def define_bucket_mappings(buckets_mappings, lookup_buckets, use_buckets, settings):
    """
    Function to populate bucket mapping

    :param buckets_mappings:
    :return:
    """
    for bucket in lookup_buckets:
        bucket_config = lookup_bucket_config(bucket.lookup, settings.session)
        bucket.mappings.update(
            {
                bucket.logical_name: bucket_config["Name"],
                "Arn": bucket_config["Arn"],
            }
        )
        buckets_mappings.update({bucket.logical_name: bucket.mappings})
        bucket_key = get_bucket_kms_key_from_config(bucket_config)
        if bucket_key:
            LOG.info(f"Identified CMK {bucket_key} to be default key for encryption")
            buckets_mappings[bucket.logical_name]["KmsKey"] = bucket_key
        else:
            LOG.info(
                "No KMS Key has been identified to encrypt the bucket. Won't grant service access."
            )
    for bucket in use_buckets:
        if bucket.use.startswith("arn:aws"):
            bucket_arn = bucket.use
            try:
                bucket_name = re.match(
                    r"(?:arn:aws(?:[a-z-]+)?:s3:{3})(?P<bucketname>[a-z0-9-.]+.$)",
                    bucket_arn,
                ).group("bucketname")
            except AttributeError:
                raise ValueError(
                    "Could not determine the bucket name from the give ARN",
                    bucket.use,
                )
            LOG.info(f"Determined bucket name is {bucket_name} from arn {bucket_arn}")
        else:
            bucket_name = bucket.use
            bucket_arn = f"arn:aws:s3:::{bucket_name}"
            LOG.warning(
                "In the absence of a full ARN, assuming partition to be `aws`. Set full ARN to rectify"
            )
            LOG.warning(f"ARN for {bucket_name} is set to {bucket_arn}")
        buckets_mappings.update(
            {
                bucket.logical_name: {
                    bucket.logical_name: bucket_name,
                    "Arn": bucket_arn,
                }
            }
        )


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
    access = {objects_key: "RW", bucket_key: "ListOnly"}
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
            target[0].template,
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
            target[0].template,
            bucket,
            objects_perms,
            access[objects_key],
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
            if keyisset("KmsKey", mappings[bucket.logical_name]):
                kms_perms = generate_resource_permissions(
                    f"{bucket.logical_name}KmsKey",
                    KMS_ACCESS_TYPES,
                    arn=FindInMap("s3", bucket.logical_name, "KmsKey"),
                )
                add_iam_policy_to_service_task_role(
                    target[0].template,
                    bucket,
                    kms_perms,
                    "EncryptDecrypt",
                    select_services,
                )
            define_lookup_buckets_access(bucket, target, select_services)


def s3_to_ecs(xresources, services_stack, res_root_stack, settings):
    """
    Function to handle permissions assignment to ECS services.

    :param xresources: x-sqs queues defined in compose file
    :param ecs_composex.common.stack.ComposeXStack services_stack: services root stack
    :param ecs_composex.common.stack.ComposeXStack res_root_stack: s3 root stack
    :param ecs_composex.common.settings.ComposeXSettings settings: ComposeX Settings for execution
    :return:
    """
    buckets_mappings = {}
    if res_root_stack.is_void:
        key = MOD_KEY
    else:
        key = res_root_stack.title
    settings.mappings[key] = buckets_mappings
    new_resources = [
        xresources[name]
        for name in xresources
        if not xresources[name].lookup and not xresources[name].use
    ]
    lookup_buckets = [
        xresources[name]
        for name in xresources
        if xresources[name].lookup and not xresources[name].use
    ]
    use_buckets = [xresources[name] for name in xresources if xresources[name].use]
    define_bucket_mappings(buckets_mappings, lookup_buckets, use_buckets, settings)
    LOG.debug(dumps(buckets_mappings, indent=4))
    for res in new_resources:
        LOG.info(f"Creating {res.name} as {res.logical_name}")
        handle_new_resources(
            res,
            services_stack,
            res_root_stack,
        )
    for res in lookup_buckets:
        assign_lookup_buckets(res, buckets_mappings)
    for res in use_buckets:
        assign_lookup_buckets(res, buckets_mappings)
