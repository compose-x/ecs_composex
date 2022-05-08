# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template
    from .kinesis_firehose_stack import DeliveryStream

from troposphere import Sub
from troposphere.firehose import DeliveryStream
from troposphere.logs import LogGroup

from ecs_composex.common import build_template
from ecs_composex.resources_import import import_record_properties

from .kinesis_firehose_iam_helpers import set_replace_iam_role


def create_new_stream(stream: DeliveryStream) -> None:
    """
    Imports the settings from CFN Definitions and define the CFN Resource from properties

    :param DeliveryStream stream:
    """
    props = import_record_properties(
        stream.properties,
        DeliveryStream,
        ignore_missing_required=True,
        ignore_missing_sub_required=True,
    )
    stream.cfn_resource = DeliveryStream(stream.logical_name, **props)
    stream.log_group = LogGroup(
        f"{stream.logical_name}LogGroup",
        LogGroupName=Sub(f"firehose/${stream.cfn_resource}"),
    )
    set_replace_iam_role(stream)
    stream.init_outputs()
    stream.generate_outputs()


def create_streams_template(new_resources: list[DeliveryStream]) -> Template:
    """
    Function to create the root template for Firehose DeliveryStream

    :param list[DeliveryStream] new_resources:
    :return: root template
    """
    root_template = build_template("Root stack for ecs_composex.kinesis_firehose")
    for res in new_resources:
        create_new_stream(res)
        root_template.add_resource(res.cfn_resource)
        root_template.add_resource(res.iam_manager.service_linked_role)
        root_template.add_output(res.outputs)
    return root_template
