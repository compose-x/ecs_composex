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
    from troposphere import AWSHelperFn

from troposphere import Ref

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters, add_update_mapping
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.resource_settings import map_x_resource_perms_to_resource
from ecs_composex.resources_import import get_dest_resource_nested_property, skip_if

FIREHOSE_PROPERTIES = {
    "DeliveryStreamEncryptionConfigurationInput::KeyARN": KMS_KEY_ARN,
    "ExtendedS3DestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::"
    "AWSKMSKeyARN": KMS_KEY_ARN,
    "RedshiftDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::"
    "AWSKMSKeyARN": KMS_KEY_ARN,
    "ElasticsearchDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::"
    "AWSKMSKeyARN": KMS_KEY_ARN,
    "AmazonopensearchserviceDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::"
    "AWSKMSKeyARN": KMS_KEY_ARN,
    "SplunkDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::"
    "AWSKMSKeyARN": KMS_KEY_ARN,
    "HttpEndpointDestinationConfiguration::EncryptionConfiguration::KMSEncryptionConfig::"
    "AWSKMSKeyARN": KMS_KEY_ARN,
}


def set_for_new_kms_key(
    prop_attr, resource_id, dest_resource, dest_resource_stack
) -> AWSHelperFn:
    add_parameters(dest_resource_stack.stack_template, [resource_id["ImportParameter"]])
    setattr(
        prop_attr[0],
        prop_attr[1],
        Ref(resource_id["ImportParameter"]),
    )
    setattr(prop_attr[0], "KeyType", "CUSTOMER_MANAGED_CMK")
    dest_resource.stack.Parameters.update(
        {resource_id["ImportParameter"].title: resource_id["ImportValue"]}
    )
    return Ref(resource_id["ImportParameter"])


def set_for_lookup_kms_key(
    prop_attr, resource, resource_id, dest_resource, settings
) -> AWSHelperFn:
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
    return resource_id["ImportValue"]


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
            arn_pointer = set_for_new_kms_key(
                prop_attr, resource_id, dest_resource, dest_resource_stack
            )
        elif not resource.cfn_resource and resource.mappings:
            arn_pointer = set_for_lookup_kms_key(
                prop_attr, resource, resource_id, dest_resource, settings
            )
        else:
            raise ValueError("Unable to determine if the KMS Key is new or lookup")

        map_x_resource_perms_to_resource(
            dest_resource,
            arn_value=arn_pointer,
            access_definition="Direct",
            access_subkey="kinesis_firehose",
            resource_policies=get_access_types(resource.module.mod_key),
            resource_mapping_key=resource.module.mapping_key,
        )
        dest_resource.ensure_iam_policies_dependencies()
