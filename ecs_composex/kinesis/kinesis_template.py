# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import NoValue, Tags
from troposphere.kinesis import Stream, StreamEncryption

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_resource,
    build_template,
)
from ecs_composex.resources_import import import_record_properties


def handle_encryption(stream):
    """
    Function to define the encryption

    :param stream:
    :return:
    """
    return StreamEncryption(
        EncryptionType="KMS",
        KeyId=stream.properties["StreamEncryption"]["KeyId"],
    )


def create_new_stream(stream):
    """
    Function to create the new Kinesis stream
    :param ecs_composex.kinesis.kinesis_stack.Stream stream:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    props = import_record_properties(stream.properties, Stream)
    stream_mode = set_else_none("StreamModeDetails", props)
    if (
        keyisset("ShardCount", props)
        and stream_mode
        and stream_mode.StreamMode == "ON_DEMAND"
    ):
        LOG.warning(
            "{}.{} - ShardCount can't be set with StreamModeDetails.StreamMode ON_DEMAND."
            " Setting to AWS::NoValue".format(stream.module.res_key, stream.name)
        )
        props["ShardCount"] = NoValue
    else:
        if not keyisset("ShardCount", stream.properties) and (
            not stream_mode or (stream_mode and stream_mode.StreamMode == "PROVISIONED")
        ):
            LOG.warning(
                "{}.{} - ShardCount must be set if StreamModeDetails isn't set or is set to PROVISIONED."
                " Defaulting to 1".format(stream.module.res_key, stream.name)
            )
            props["ShardCount"] = 1

    props["Tags"] = Tags(Name=stream.logical_name, ComposeName=stream.name)
    stream.cfn_resource = Stream(stream.logical_name, **props)
    stream.init_outputs()
    stream.generate_outputs()


def create_streams_template(new_resources, settings):
    """
    Function to create the root template for Kinesis streams

    :param list<ecs_composex.kinesis.kinesis_stack.Stream> new_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    root_template = build_template("Root stack for ecs_composex.kinesis")
    for res in new_resources:
        create_new_stream(res)
        add_resource(root_template, res.cfn_resource)
        add_outputs(root_template, res.outputs)
    return root_template
