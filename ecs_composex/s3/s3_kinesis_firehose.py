#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Updates x-kinesis_firehose fields and properties, IAM policies for Firehose::DeliveryStream
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .s3_params import S3_BUCKET_ARN

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from .s3_bucket import Bucket
    from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream

from troposphere import Ref

from ecs_composex.common import LOG, add_parameters, add_update_mapping
from ecs_composex.resources_import import get_dest_resource_nested_property

FIREHOSE_PROPERTIES = {
    "S3DestinationConfiguration::BucketARN": S3_BUCKET_ARN,
    "ExtendedS3DestinationConfiguration::BucketARN": S3_BUCKET_ARN,
    "ExtendedS3DestinationConfiguration::S3BackupConfiguration::BucketARN": S3_BUCKET_ARN,
    "RedshiftDestinationConfiguration::S3BackupConfiguration::BucketARN": S3_BUCKET_ARN,
    "ElasticsearchDestinationConfiguration::S3BackupConfiguration::BucketARN": S3_BUCKET_ARN,
    "AmazonopensearchserviceDestinationConfiguration::S3BackupConfiguration::BucketARN": S3_BUCKET_ARN,
    "SplunkDestinationConfiguration::S3BackupConfiguration::BucketARN": S3_BUCKET_ARN,
    "HttpEndpointDestinationConfiguration::S3BackupConfiguration::BucketARN": S3_BUCKET_ARN,
}


def s3_to_firehose(
    bucket: Bucket,
    dest_resource: DeliveryStream,
    dest_resource_stack,
    settings: ComposeXSettings,
) -> None:
    """
    Updates
    :param Bucket bucket:
    :param DeliveryStream dest_resource:
    :param dest_resource_stack:
    :param settings:
    :return:
    """
    if not dest_resource.cfn_resource:
        LOG.error(
            f"{dest_resource.module.res_key}.{dest_resource.name} - Not a new resource"
        )
    for prop_path, bucket_param in FIREHOSE_PROPERTIES.items():
        prop_attr = get_dest_resource_nested_property(
            prop_path, dest_resource.cfn_resource
        )
        if not prop_attr:
            continue
        prop_attr_value = getattr(prop_attr[0], prop_attr[1])
        if bucket.name not in prop_attr_value:
            continue
        bucket_id = bucket.attributes_outputs[bucket_param]
        if bucket.cfn_resource:
            add_parameters(
                dest_resource_stack.stack_template, [bucket_id["ImportParameter"]]
            )
            setattr(
                prop_attr[0],
                prop_attr[1],
                Ref(bucket_id["ImportParameter"]),
            )
            dest_resource.stack.Parameters.update(
                {bucket_id["ImportParameter"].title: bucket_id["ImportValue"]}
            )
        elif not bucket.cfn_resource and bucket.mappings:
            add_update_mapping(
                dest_resource.stack.stack_template,
                bucket.module.mapping_key,
                settings.mappings[bucket.module.mapping_key],
            )
            setattr(prop_attr[0], prop_attr[1], bucket_id["ImportValue"])
