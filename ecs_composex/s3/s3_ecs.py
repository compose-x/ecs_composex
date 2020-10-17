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
from troposphere.s3 import Bucket

from ecs_composex.common import LOG, NONALPHANUM, keyisset
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resource_permissions import (
    apply_iam_based_resources,
    add_iam_policy_to_service_task_role,
)
from ecs_composex.resource_settings import (
    generate_resource_envvars,
    generate_resource_permissions,
)
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.s3.s3_params import S3_BUCKET_NAME
from ecs_composex.s3.s3_perms import ACCESS_TYPES, generate_s3_permissions
from ecs_composex.s3.s3_aws import lookup_bucket_config
from ecs_composex.kms.kms_perms import ACCESS_TYPES as KMS_ACCESS_TYPES


def handle_new_buckets(
    xresources,
    services_families,
    services_stack,
    res_root_stack,
    l_buckets,
    nested=False,
):
    buckets_r = []
    if res_root_stack.is_void:
        return
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if isinstance(s_resources[resource_name], Bucket):
            buckets_r.append(s_resources[resource_name].title)
        elif issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_buckets(
                xresources,
                services_families,
                services_stack,
                s_resources[resource_name],
                l_buckets,
                nested=True,
            )

    for bucket_name in xresources:
        if bucket_name in buckets_r or NONALPHANUM.sub("", bucket_name) in buckets_r:
            perms = generate_s3_permissions(
                NONALPHANUM.sub("", bucket_name), S3_BUCKET_NAME
            )
            envvars = generate_resource_envvars(
                bucket_name, xresources[bucket_name], S3_BUCKET_NAME
            )
            apply_iam_based_resources(
                xresources[bucket_name],
                services_families,
                services_stack,
                res_root_stack,
                envvars,
                perms,
                nested,
            )
            del l_buckets[bucket_name]


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


def define_bucket_access(bucket, access, service_template, service_family, family_wide):
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
    elif isinstance(access, dict):
        if not keyisset(objects_key, access) or not keyisset(bucket_key, access):
            raise KeyError("You must define at least bucket or object access")
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
    define_bucket_access(
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
    l_buckets = xresources.copy()
    new_buckets = [
        xresources[name]
        for name in xresources
        if xresources[name].properties and not xresources[name].lookup
    ]
    lookup_buckets = [
        xresources[name] for name in xresources if xresources[name].lookup
    ]
    define_bucket_mappings(buckets_mappings, lookup_buckets, settings)
    LOG.debug(dumps(buckets_mappings, indent=4))
    for res in new_buckets:
        LOG.debug(f"Creating {res.name} as {res.logical_name}")
        # handle_new_buckets(
        #     xresources, services_families, services_stack, res_root_stack, l_buckets
        # )
    for res in lookup_buckets:
        for service_def in res.services:
            assign_lookup_buckets(
                res, buckets_mappings, service_def, services_stack, services_families
            )
