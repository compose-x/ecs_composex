# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to control S3 stack
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from botocore.exceptions import ClientError
from compose_x_common.aws.s3 import S3_BUCKET_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere.s3 import Bucket as CfnBucket

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.s3.s3_bucket import Bucket
from ecs_composex.s3.s3_params import (
    CONTROL_CLOUD_ATTR_MAPPING,
    S3_BUCKET_ARN,
    S3_BUCKET_KMS_KEY,
    S3_BUCKET_KMS_KEY_ARN,
    S3_BUCKET_NAME,
)
from ecs_composex.s3.s3_template import create_s3_template


def get_bucket_config(bucket: Bucket, resource_id: str) -> dict:
    """

    :param ecs_composex.s3.s3_bucket.Bucket bucket:
    :param str resource_id:
    """
    bucket_config = {
        S3_BUCKET_NAME: resource_id,
        S3_BUCKET_ARN: bucket.arn,
    }
    client = bucket.lookup_session.client("s3")

    try:
        encryption_r = client.get_bucket_encryption(Bucket=resource_id)
        encryption_attributes = attributes_to_mapping(
            encryption_r, CONTROL_CLOUD_ATTR_MAPPING
        )
        if keyisset(
            CONTROL_CLOUD_ATTR_MAPPING[S3_BUCKET_KMS_KEY],
            encryption_attributes,
        ):
            bucket_config[S3_BUCKET_KMS_KEY] = encryption_attributes[S3_BUCKET_KMS_KEY]

    except ClientError as error:
        if (
            not error.response["Error"]["Code"]
            == "ServerSideEncryptionConfigurationNotFoundError"
        ):
            raise
        LOG.warning(error.response["Error"]["Message"])
    return bucket_config


def define_bucket_mappings(
    lookup_buckets: list[Bucket], settings: ComposeXSettings, module: XResourceModule
) -> None:
    """
    Method to define CFN Mappings for the lookup buckets

    :param list[Bucket] lookup_buckets:
    :param ComposeXSettings settings:
    :param module:
    """
    for bucket in lookup_buckets:
        bucket.init_outputs()
        bucket.lookup_resource(
            S3_BUCKET_ARN_RE, get_bucket_config, CfnBucket.resource_type, "s3"
        )
        settings.mappings[module.mapping_key].update(
            {bucket.logical_name: bucket.mappings}
        )
        if not keyisset(S3_BUCKET_KMS_KEY, bucket.lookup_properties):
            LOG.info(
                f"{module.res_key}.{bucket.name} - No CMK Key identified. Not KMS permissions to set."
            )
        else:
            LOG.info(
                f"{module.res_key}.{bucket.name} - "
                f"CMK identified {bucket.lookup_properties[S3_BUCKET_KMS_KEY]}."
            )
            key_arn_r = bucket.lookup_session.client("kms").describe_key(
                KeyId=bucket.lookup_properties[S3_BUCKET_KMS_KEY]
            )["KeyMetadata"]["Arn"]
            bucket.lookup_properties.update({S3_BUCKET_KMS_KEY_ARN: key_arn_r})
            LOG.info(
                f"{module.res_key}.{bucket.name} - "
                f"CMK ARN - {bucket.lookup_properties[S3_BUCKET_KMS_KEY_ARN]}"
            )
            bucket.add_new_output_attribute(
                S3_BUCKET_KMS_KEY_ARN,
                (
                    f"{bucket.logical_name}{S3_BUCKET_KMS_KEY_ARN.return_value}",
                    None,
                    None,
                    S3_BUCKET_KMS_KEY_ARN.return_value,
                ),
            )
            bucket.add_new_output_attribute(
                S3_BUCKET_KMS_KEY,
                (
                    f"{bucket.logical_name}{S3_BUCKET_KMS_KEY.return_value}",
                    None,
                    None,
                    S3_BUCKET_KMS_KEY.return_value,
                ),
            )

        bucket.generate_cfn_mappings_from_lookup_properties()
        bucket.generate_outputs()


class XStack(ComposeXStack):
    """
    Class to handle S3 buckets
    """

    def __init__(
        self, title: str, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            if not keyisset(module.mapping_key, settings.mappings):
                settings.mappings[module.mapping_key] = {}
            define_bucket_mappings(module.lookup_resources, settings, module)
        if module.new_resources:
            stack_template = build_template(f"Root template for {settings.name}.s3")
            super().__init__(module.mapping_key, stack_template, **kwargs)
            create_s3_template(module.new_resources, stack_template)
            self.parent_stack = settings.root_stack
        else:
            self.is_void = True
        for resource in module.resources_list:
            resource.stack = self
