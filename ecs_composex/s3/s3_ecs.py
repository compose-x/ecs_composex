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

"""
Functions to pass permissions to Services to access S3 buckets.
"""

from json import dumps

from troposphere import FindInMap, Sub

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kms.kms_perms import ACCESS_TYPES as KMS_ACCESS_TYPES
from ecs_composex.resource_permissions import (
    add_iam_policy_to_service_task_role,
    add_iam_policy_to_service_task_role_v2,
)
from ecs_composex.resource_settings import (
    generate_resource_permissions,
    generate_export_strings,
)
from ecs_composex.s3.s3_aws import lookup_bucket_config
from ecs_composex.s3.s3_params import S3_BUCKET_ARN, S3_BUCKET_NAME
from ecs_composex.s3.s3_perms import ACCESS_TYPES


def assign_service_permissions_to_bucket(
    bucket, access, service_template, service_family, family_wide
):
    bucket_key = "bucket"
    objects_key = "objects"
    bucket_arn_import = generate_export_strings(bucket.logical_name, S3_BUCKET_ARN)
    bucket_name_import = generate_export_strings(bucket.logical_name, S3_BUCKET_NAME)
    bucket.generate_resource_envvars(None, bucket_name_import)
    if keyisset(bucket_key, access):
        bucket_perms = generate_resource_permissions(
            f"BucketAccess{bucket.logical_name}",
            ACCESS_TYPES[bucket_key],
            None,
            arn=bucket_arn_import,
        )
        add_iam_policy_to_service_task_role(
            service_template,
            bucket,
            bucket_perms,
            access[bucket_key],
            service_family,
            family_wide,
        )
    if keyisset(objects_key, access):
        objects_perms = generate_resource_permissions(
            f"ObjectsAccess{bucket.logical_name}",
            ACCESS_TYPES[objects_key],
            None,
            arn=Sub("${BucketArn}/*", BucketArn=bucket_arn_import),
        )
        add_iam_policy_to_service_task_role(
            service_template,
            bucket,
            objects_perms,
            access[objects_key],
            service_family,
            family_wide,
        )


def assign_new_bucket_to_services(bucket, nested=False):
    """
    Function to assign the bucket services permissions to access the s3 bucket.
    :param bucket:
    :param bool nested:
    :return:
    """
    bucket_key = "bucket"
    objects_key = "objects"
    select_services = []
    access = {objects_key: "RW", bucket_key: "ListOnly"}
    for target in bucket.families_targets:
        if not target[1] and target[2]:
            LOG.debug(
                f"Resource {bucket.name} only applies to {target[2]} in family {target[0].name}"
            )
            select_services = target[2]
        elif target[1]:
            LOG.debug(f"Resource {bucket.name} applies to family {target[0].name}")
            select_services = target[0].services
        if select_services:
            if not isinstance(target[3], str):
                LOG.warn(
                    f"No permissions associated for {bucket.name} to {target[0].name}. Setting default."
                )
            else:
                access = target[3]
            assign_service_permissions_to_bucket(
                bucket, target[0], select_services, access, S3_BUCKET_ARN
            )


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
    assign_new_bucket_to_services(resource, nested)


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


def define_bucket_mappings(buckets_mappings, buckets, settings):
    """
    Function to populate bucket mapping

    :param buckets_mappings:
    :return:
    """
    for bucket in buckets:
        bucket_config = lookup_bucket_config(bucket.lookup, settings.session)
        buckets_mappings.update(
            {
                bucket.logical_name: {
                    "Name": bucket_config["Name"],
                    "Arn": bucket_config["Arn"],
                }
            }
        )
        bucket_key = get_bucket_kms_key_from_config(bucket_config)
        if bucket_key:
            LOG.info(f"Identified CMK {bucket_key} to be default key for encryption")
            buckets_mappings[bucket.logical_name]["KmsKey"] = bucket_key
        else:
            LOG.info(
                "No KMS Key has been identified to encrypt the bucket. Won't grant service access."
            )


def define_lookup_buckets_access(bucket, target, services):
    """
    Function to create the IAM policy for the service access to bucket

    :param bucket:
    :return:
    """
    bucket_key = "bucket"
    objects_key = "objects"
    access = {objects_key: "RW", bucket_key: "ListOnly"}
    if isinstance(target[3], str):
        LOG.warn(
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
    bucket.generate_resource_envvars(
        None, arn=FindInMap("s3", bucket.logical_name, "Name")
    )
    if keyisset(bucket_key, access):
        bucket_perms = generate_resource_permissions(
            f"BucketAccess{bucket.logical_name}",
            ACCESS_TYPES[bucket_key],
            None,
            arn=FindInMap("s3", bucket.logical_name, "Arn"),
        )
        add_iam_policy_to_service_task_role_v2(
            target[0].template, bucket, bucket_perms, access[bucket_key], services
        )
    if keyisset(objects_key, access):
        objects_perms = generate_resource_permissions(
            f"ObjectsAccess{bucket.logical_name}",
            ACCESS_TYPES[objects_key],
            None,
            arn=Sub(
                "${BucketArn}/*", BucketArn=FindInMap("s3", bucket.logical_name, "Arn")
            ),
        )
        add_iam_policy_to_service_task_role_v2(
            target[0].template, bucket, objects_perms, access[objects_key], services
        )


def assign_lookup_buckets(bucket, mappings):
    """
    Function to add the lookup bucket to service access

    :param ecs_composex.s3.s3_stacks.Bucket bucket:
    :param dict mappings:
    """
    if not keyisset(bucket.logical_name, mappings):
        LOG.warn(f"Bucket {bucket.logical_name} was not found in mappings. Skipping")
        return
    bucket_key = "bucket"
    objects_key = "objects"
    select_services = []
    access = {objects_key: "RW", bucket_key: "ListOnly"}
    for target in bucket.families_targets:
        if not target[1] and target[2]:
            LOG.debug(
                f"Resource {bucket.name} only applies to {target[2]} in family {target[0].name}"
            )
            select_services = target[2]
        elif target[1]:
            LOG.debug(f"Resource {bucket.name} applies to family {target[0].name}")
            select_services = target[0].services
        if select_services:
            target[0].template.add_mapping("s3", mappings)
            if not keyisset("access", target[3]) or isinstance(target[3], str):
                LOG.warn(
                    f"No permissions associated for {target[0].name}. Setting default."
                )
            else:
                access = target[3]
            assign_service_permissions_to_bucket(
                bucket, target[0], select_services, access, S3_BUCKET_ARN
            )
            if keyisset("KmsKey", mappings[bucket.logical_name]):
                kms_perms = generate_resource_permissions(
                    f"{bucket.logical_name}KmsKey",
                    KMS_ACCESS_TYPES,
                    None,
                    arn=FindInMap("s3", bucket.logical_name, "KmsKey"),
                )
                add_iam_policy_to_service_task_role_v2(
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
    new_resources = [
        xresources[name] for name in xresources if not xresources[name].lookup
    ]
    lookup_buckets = [
        xresources[name] for name in xresources if xresources[name].lookup
    ]
    define_bucket_mappings(buckets_mappings, lookup_buckets, settings)
    LOG.debug(dumps(buckets_mappings, indent=4))
    if new_resources and res_root_stack.title not in services_stack.DependsOn:
        services_stack.DependsOn.append(res_root_stack.title)
        LOG.info(f"Added dependency between services and {res_root_stack.title}")
    for res in new_resources:
        LOG.debug(f"Creating {res.name} as {res.logical_name}")
        handle_new_resources(
            res,
            services_stack,
            res_root_stack,
        )
    for res in lookup_buckets:
        for service_def in res.services:
            assign_lookup_buckets(res, buckets_mappings)
