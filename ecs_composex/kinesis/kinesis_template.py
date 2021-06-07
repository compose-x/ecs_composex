#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from troposphere import Tags
from troposphere.kinesis import Stream, StreamEncryption

from ecs_composex.common import LOG, build_template, keyisset
from ecs_composex.resources_import import import_record_properties


def handle_encryption(stream):
    """
    Function to define the encryption

    :param stream:
    :return:
    """
    return StreamEncryption(
        EncryptionType="KMS", KeyId=stream.properties["StreamEncryption"]["KeyId"]
    )


def create_new_stream(stream):
    """
    Function to create the new Kinesis stream
    :param ecs_composex.kinesis.kinesis_stack.Stream stream:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    props = import_record_properties(stream.properties, Stream)
    if not keyisset("ShardCount", stream.properties):
        LOG.warning("ShardCount must be set. Defaulting to 1")
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
        root_template.add_resource(res.cfn_resource)
        root_template.add_output(res.outputs)
    return root_template
