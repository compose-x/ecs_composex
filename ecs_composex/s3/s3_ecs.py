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
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.kms.kms_perms import ACCESS_TYPES as KMS_ACCESS_TYPES
from ecs_composex.resource_permissions import (
    add_iam_policy_to_service_task_role,
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


def assign_new_bucket_to_services(
    bucket, services_stack, services_families, res_root_stack
):
    """
    Function to assign the bucket services permissions to access the s3 bucket.
    :param bucket:
    :param services_stack:
    :param services_families:
    :param res_root_stack:
    :return:
    """
    bucket_key = "bucket"
    objects_key = "objects"
    access = {objects_key: "RW", bucket_key: "ListOnly"}
    for service in bucket.services:
        if not keyisset("access", service) or isinstance(service["access"], str):
            LOG.warn(
                f"No permissions associated for {service['name']}. Setting default."
            )
        else:
            access = service["access"]
        service_family = get_service_family_name(services_families, service["name"])
        if service_family not in services_stack.stack_template.resources:
            raise AttributeError(
                f"No service {service_family} present in services stack"
            )
        family_wide = True if service["name"] in services_families else False
        service_stack = services_stack.stack_template.resources[service_family]
        service_template = service_stack.stack_template
        assign_service_permissions_to_bucket(
            bucket, access, service_template, service_family, family_wide
        )


def handle_new_buckets(
    resource,
    services_families,
    services_stack,
    res_root_stack,
    nested=False,
):
    """

    :param resource: The resource
    :type resource: ecs_composex.s3.s3_stack.Bucket
    :param services_families:
    :param services_stack:
    :param res_root_stack:
    :param nested:
    :return:
    """
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_buckets(
                resource,
                services_families,
                services_stack,
                s_resources[resource_name],
                nested=True,
            )
        else:
            assign_new_bucket_to_services(
                resource, services_stack, services_families, res_root_stack
            )


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


def define_lookup_buckets_access(
    bucket, access, service_template, service_family, family_wide
):
    """
    Function to create the IAM policy for the service access to bucket

    :param bucket:
    :param access:
    :param troposphere.Template service_template:
    :param str service_family:
    :param bool family_wide:
    :return:
    """
    bucket_key = "bucket"
    objects_key = "objects"
    if isinstance(access, str):
        LOG.warn(
            "For s3 buckets, you should define a dict for access, with bucket and/or object policies separate."
            " Using default RW Objects and ListBucket"
        )
        access = {objects_key: "RW", bucket_key: "ListOnly"}
    elif (
        isinstance(access, dict)
        and not keyisset(objects_key, access)
        or not keyisset(bucket_key, access)
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
            arn=Sub(
                "${BucketArn}/*", BucketArn=FindInMap("s3", bucket.logical_name, "Arn")
            ),
        )
        add_iam_policy_to_service_task_role(
            service_template,
            bucket,
            objects_perms,
            access[objects_key],
            service_family,
            family_wide,
        )


def assign_lookup_buckets(bucket, mappings, service, services_stack, services_families):
    """
    Function to add the lookup bucket to service access

    :param ecs_composex.s3.s3_stacks.Bucket bucket:
    :param dict mappings:
    :param dict service:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param dict services_families:
    """
    if not keyisset(bucket.logical_name, mappings):
        LOG.warn(f"Bucket {bucket.logical_name} was not found in mappings. Skipping")
        return
    service_family = get_service_family_name(services_families, service["name"])
    if service_family not in services_stack.stack_template.resources:
        raise AttributeError(f"No service {service_family} present in services stack")
    family_wide = True if service["name"] in services_families else False
    service_stack = services_stack.stack_template.resources[service_family]
    service_stack.stack_template.add_mapping("s3", mappings)
    service_template = service_stack.stack_template
    if keyisset("KmsKey", mappings[bucket.logical_name]):
        kms_perms = generate_resource_permissions(
            f"{bucket.logical_name}KmsKey",
            KMS_ACCESS_TYPES,
            None,
            arn=FindInMap("s3", bucket.logical_name, "KmsKey"),
        )
        add_iam_policy_to_service_task_role(
            service_template,
            bucket,
            kms_perms,
            "EncryptDecrypt",
            service_family,
            family_wide,
        )
    if not keyisset("access", service):
        LOG.error(f"No access defined for s3 bucket {bucket.name}")
        return
    define_lookup_buckets_access(
        bucket, service["access"], service_template, service_family, family_wide
    )


def s3_to_ecs(xresources, services_stack, services_families, res_root_stack, settings):
    """
    Function to handle permissions assignment to ECS services.

    :param xresources: x-sqs queues defined in compose file
    :param ecs_composex.common.stack.ComposeXStack services_stack: services root stack
    :param services_families: services families
    :param ecs_composex.common.stack.ComposeXStack res_root_stack: s3 root stack
    :param ecs_composex.common.settings.ComposeXSettings settings: ComposeX Settings for execution
    :return:
    """
    buckets_mappings = {}
    new_buckets = [
        xresources[name] for name in xresources if not xresources[name].lookup
    ]
    lookup_buckets = [
        xresources[name] for name in xresources if xresources[name].lookup
    ]
    define_bucket_mappings(buckets_mappings, lookup_buckets, settings)
    LOG.debug(dumps(buckets_mappings, indent=4))
    for res in new_buckets:
        LOG.debug(f"Creating {res.name} as {res.logical_name}")
        handle_new_buckets(
            res,
            services_families,
            services_stack,
            res_root_stack,
        )
    for res in lookup_buckets:
        for service_def in res.services:
            assign_lookup_buckets(
                res, buckets_mappings, service_def, services_stack, services_families
            )
