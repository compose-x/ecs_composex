#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Updates x-kinesis_firehose fields and properties, IAM policies for Firehose::DeliveryStream
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .kinesis_params import STREAM_ARN

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import Ref

from ecs_composex.common import LOG, add_parameters, add_update_mapping
from ecs_composex.resources_import import get_dest_resource_nested_property

FIREHOSE_PROPERTIES = {"KinesisStreamSourceConfiguration::KinesisStreamARN": STREAM_ARN}


def kinesis_to_firehose(
    stream, dest_resource, dest_resource_stack, settings: ComposeXSettings
) -> None:
    """
    Updates
    :param stream:
    :param dest_resource:
    :param dest_resource_stack:
    :param settings:
    :return:
    """
    if not dest_resource.cfn_resource:
        LOG.error(
            f"{dest_resource.module.res_key}.{dest_resource.name} - Not a new resource"
        )
    for prop_path, stream_param in FIREHOSE_PROPERTIES.items():
        prop_attr = get_dest_resource_nested_property(
            prop_path, dest_resource.cfn_resource
        )
        if not prop_attr:
            continue
        prop_attr_value = getattr(prop_attr[0], prop_attr[1])
        if stream.name not in prop_attr_value:
            continue
        stream_id = stream.attributes_outputs[stream_param]
        if stream.cfn_resource:
            add_parameters(
                dest_resource_stack.stack_template, [stream_id["ImportParameter"]]
            )
            setattr(
                prop_attr[0],
                prop_attr[1],
                Ref(stream_id["ImportParameter"]),
            )
            dest_resource.stack.Parameters.update(
                {stream_id["ImportParameter"].title: stream_id["ImportValue"]}
            )
        elif not stream.cfn_resource and stream.mappings:
            add_update_mapping(
                dest_resource.stack.stack_template,
                stream.module.mapping_key,
                settings.mappings[stream.module.mapping_key],
            )
            setattr(prop_attr[0], prop_attr[1], stream_id["ImportValue"])
