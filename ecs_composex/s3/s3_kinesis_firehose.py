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

from ecs_composex.common.logging import LOG
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.resource_settings import map_x_resource_perms_to_resource
from ecs_composex.resources_import import get_dest_resource_nested_property, skip_if

from ..common.troposphere_tools import add_parameters, add_update_mapping

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
    resource: Bucket,
    dest_resource: DeliveryStream,
    dest_resource_stack,
    settings: ComposeXSettings,
) -> None:
    """
    Updates
    :param Bucket resource:
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
        if skip_if(resource, prop_attr):
            continue
        bucket_id = resource.attributes_outputs[bucket_param]
        if resource.cfn_resource:
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
            arn_pointer = Ref(bucket_id["ImportParameter"])
        elif not resource.cfn_resource and resource.mappings:
            add_update_mapping(
                dest_resource.stack.stack_template,
                resource.module.mapping_key,
                settings.mappings[resource.module.mapping_key],
            )
            setattr(prop_attr[0], prop_attr[1], bucket_id["ImportValue"])
            arn_pointer = bucket_id["ImportValue"]
        else:
            raise ValueError(
                resource.module.mapping_key,
                resource.name,
                "Unable to determine if new or lookup",
            )
        map_x_resource_perms_to_resource(
            dest_resource,
            arn_value=arn_pointer,
            access_definition="s3destination",
            access_subkey="kinesis_firehose",
            resource_policies=get_access_types(resource.module.mod_key),
            resource_mapping_key=resource.module.mapping_key,
        )
        dest_resource.ensure_iam_policies_dependencies()
