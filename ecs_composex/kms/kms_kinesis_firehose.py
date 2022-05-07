#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Updates x-kinesis_firehose fields and properties, IAM policies for Firehose::DeliveryStream
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .kms_params import KMS_KEY_ARN

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from .kms_stack import KmsKey
    from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream

from troposphere import Ref

from ecs_composex.common import LOG, add_parameters, add_update_mapping
from ecs_composex.resources_import import get_dest_resource_nested_property

FIREHOSE_PROPERTIES = {
    "DeliveryStreamEncryptionConfigurationInput::KeyARN": KMS_KEY_ARN,
    "ExtendedS3DestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::AWSKMSKeyARN": KMS_KEY_ARN,
    "RedshiftDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::AWSKMSKeyARN": KMS_KEY_ARN,
    "ElasticsearchDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::AWSKMSKeyARN": KMS_KEY_ARN,
    "AmazonopensearchserviceDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::AWSKMSKeyARN": KMS_KEY_ARN,
    "SplunkDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::AWSKMSKeyARN": KMS_KEY_ARN,
    "HttpEndpointDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::AWSKMSKeyARN": KMS_KEY_ARN,
}


def skip_if(resource, prop_attr) -> bool:
    if not prop_attr:
        return True
    prop_attr_value = getattr(prop_attr[0], prop_attr[1])
    if not isinstance(prop_attr_value, str):
        return True
    if not prop_attr_value.startswith(resource.module.res_key):
        return True
    if resource.name not in prop_attr_value.split(resource.module.res_key)[-1]:
        return True
    return False


def kms_to_firehose(
    resource: KmsKey,
    dest_resource: DeliveryStream,
    dest_resource_stack,
    settings: ComposeXSettings,
) -> None:
    """
    Updates properties of the Firehose Delivery Stream with KMS key settings

    :param KmsKey resource:
    :param DeliveryStream dest_resource:
    :param dest_resource_stack:
    :param ComposeXSettings settings:
    """
    if not dest_resource.cfn_resource:
        LOG.error(
            f"{dest_resource.module.res_key}.{dest_resource.name} - Not a new resource"
        )
    for prop_path, resource_param in FIREHOSE_PROPERTIES.items():
        prop_attr = get_dest_resource_nested_property(
            prop_path, dest_resource.cfn_resource
        )
        if skip_if(resource, prop_attr):
            continue
        resource_id = resource.attributes_outputs[resource_param]
        if resource.cfn_resource:
            add_parameters(
                dest_resource_stack.stack_template, [resource_id["ImportParameter"]]
            )
            setattr(
                prop_attr[0],
                prop_attr[1],
                Ref(resource_id["ImportParameter"]),
            )
            setattr(prop_attr[0], "KeyType", "CUSTOMER_MANAGED_CMK")
            dest_resource.stack.Parameters.update(
                {resource_id["ImportParameter"].title: resource_id["ImportValue"]}
            )
        elif not resource.cfn_resource and resource.mappings:
            add_update_mapping(
                dest_resource.stack.stack_template,
                resource.module.mapping_key,
                settings.mappings[resource.module.mapping_key],
            )
            setattr(prop_attr[0], prop_attr[1], resource_id["ImportValue"])
            if resource.is_cmk:
                setattr(prop_attr[0], "KeyType", "CUSTOMER_MANAGED_CMK")
            else:
                setattr(prop_attr[0], "KeyType", "AWS_OWNED_CMK")
