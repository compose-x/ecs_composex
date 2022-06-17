# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle import/create AWS Kinesis Data Streams
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from botocore.exceptions import ClientError
from compose_x_common.aws.kinesis import KINESIS_STREAM_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.kinesis import Stream as CfnStream

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.kinesis.kinesis_params import STREAM_ARN, STREAM_ID, STREAM_KMS_KEY_ID
from ecs_composex.kinesis.kinesis_template import create_streams_template
from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream

from .kinesis_kinesis_firehose import kinesis_to_firehose


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
            STREAM_ARN: "Arn",
            STREAM_ID: "Name",
            STREAM_KMS_KEY_ID: "StreamEncryption::KeyId",
        }
        self.support_defaults = True

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

    def handle_x_dependencies(
        self, settings: ComposeXSettings, root_stack: ComposeXStack
    ) -> None:
        """
        Updates other resources and replace the values for `x-kinesis` wherever applicable.

        :param settings:
        :param root_stack:
        :return:
        """
        for resource in settings.get_x_resources(include_mappings=False):
            if not resource.cfn_resource:
                continue
            if not resource.stack:
                LOG.debug(
                    f"resource {resource.name} has no `stack` attribute defined. Skipping"
                )
                continue
            mappings = [(DeliveryStream, kinesis_to_firehose)]
            for target in mappings:
                if isinstance(resource, target[0]) or issubclass(
                    type(resource), target[0]
                ):
                    target[1](
                        self,
                        resource,
                        resource.stack,
                        settings,
                    )


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
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)
        if module.new_resources:
            stack_template = create_streams_template(module.new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in module.resources_list:
            resource.stack = self
