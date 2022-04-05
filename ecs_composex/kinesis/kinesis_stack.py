# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle import/create AWS Kinesis Data Streams
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from botocore.exceptions import ClientError
from compose_x_common.aws.kinesis import KINESIS_STREAM_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.kinesis import Stream as CfnStream

from ecs_composex.common import setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.kinesis.kinesis_params import STREAM_ARN, STREAM_ID, STREAM_KMS_KEY_ID
from ecs_composex.kinesis.kinesis_template import create_streams_template

LOG = setup_logging()


def get_stream_config(stream, account_id, resource_id):
    """
    Function to get the configuration of KMS Stream from API

    :param Stream stream:
    :param str account_id:
    :param str resource_id:
    :return:
    """
    client = stream.lookup_session.client("kinesis")
    stream_mapping = {
        STREAM_ARN: "StreamDescription::StreamARN",
        STREAM_ID: "StreamDescription::StreamName",
        STREAM_KMS_KEY_ID: "StreamDescription::KeyId",
    }
    try:
        stream_r = client.describe_stream(StreamName=resource_id)
        stream_config = attributes_to_mapping(stream_r, stream_mapping)
        return stream_config
    except client.exceptions.ResourceNotFoundException:
        return None
    except ClientError as error:
        LOG.error(error)


class Stream(ApiXResource):
    """
    Class to represent a Kinesis Stream
    """

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        super().__init__(
            name,
            definition,
            module,
            settings,
        )
        self.arn_parameter = STREAM_ARN
        self.ref_parameter = STREAM_ID
        self.cloud_control_attributes_mapping = {
            STREAM_ARN.title: "Arn",
            STREAM_ID.title: "Name",
            STREAM_KMS_KEY_ID.title: "StreamEncryption::KeyId",
        }

    def init_outputs(self):
        self.output_properties = {
            STREAM_ID: (self.logical_name, self.cfn_resource, Ref, None),
            STREAM_ARN: (
                f"{self.logical_name}{STREAM_ARN.title}",
                self.cfn_resource,
                GetAtt,
                STREAM_ARN.return_value,
            ),
        }


def resolve_lookup(
    lookup_resources: list[Stream], settings: ComposeXSettings, module: XResourceModule
) -> None:
    """
    Lookup AWS Kinesis streams and creates CFN Mappings
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        LOG.info(
            f"{resource.module.res_key}.{resource.logical_name} - Looking up AWS Resource"
        )
        resource.lookup_resource(
            KINESIS_STREAM_ARN_RE,
            get_stream_config,
            CfnStream.resource_type,
            "kinesis:stream",
        )
        LOG.info(f"{module.res_key}.{resource.name} - Matched to {resource.arn}")
        settings.mappings[module.res_key].update(
            {resource.logical_name: resource.mappings}
        )


class XStack(ComposeXStack):
    """
    Class to represent Kinesis Data Streams stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        set_resources(settings, Stream, module)
        x_resources = settings.compose_content[module.res_key].values()
        lookup_resources = set_lookup_resources(x_resources)
        if lookup_resources:
            resolve_lookup(lookup_resources, settings, module)
        new_resources = set_new_resources(x_resources, True)
        if new_resources:
            stack_template = create_streams_template(new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in x_resources:
            resource.stack = self
