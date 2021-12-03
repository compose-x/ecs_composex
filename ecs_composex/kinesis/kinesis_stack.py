#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from botocore.exceptions import ClientError
from compose_x_common.aws.kinesis import KINESIS_STREAM_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.kinesis import Stream as CfnStream

from ecs_composex.common import setup_logging
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.kinesis.kinesis_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    STREAM_ARN,
    STREAM_ID,
    STREAM_KMS_KEY_ID,
)
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
        STREAM_ARN.title: "StreamDescription::StreamARN",
        STREAM_ID.title: "StreamDescription::StreamName",
        STREAM_KMS_KEY_ID.title: "StreamDescription::KeyId",
    }
    try:
        stream_r = client.describe_stream(StreamName=resource_id)
        stream_config = attributes_to_mapping(stream_r, stream_mapping)
        return stream_config
    except client.exceptions.ResourceNotFoundException:
        return None
    except ClientError as error:
        LOG.error(error)


class Stream(XResource):
    """
    Class to represent a Kinesis Stream
    """

    policies_scaffolds = get_access_types(MOD_KEY)

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
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


class XStack(ComposeXStack):
    """
    Class to represent
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Stream, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = create_streams_template(new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            for resource in lookup_resources:
                LOG.info(
                    f"{resource.module_name}.{resource.logical_name} - Looking up AWS Resource"
                )
                resource.lookup_resource(
                    KINESIS_STREAM_ARN_RE,
                    get_stream_config,
                    CfnStream.resource_type,
                    "kinesis:stream",
                )
                settings.mappings[RES_KEY].update(
                    {resource.logical_name: resource.mappings}
                )
        for resource in x_resources:
            resource.stack = self
