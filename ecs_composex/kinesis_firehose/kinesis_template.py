# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kinesis_firehose_stack import DeliveryStream

from troposphere import Sub, firehose
from troposphere.iam import Role as IamRole

from ecs_composex.common import build_template
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.resources_import import import_record_properties

from .kinesis_firehose_iam_helpers import set_replace_iam_role


def create_new_stream(stream: DeliveryStream) -> None:
    """
    Imports the settings from CFN Definitions and define the CFN Resource from properties

    :param DeliveryStream stream:
    """
    props = import_record_properties(
        stream.properties,
        firehose.DeliveryStream,
        ignore_missing_required=True,
        ignore_missing_sub_required=True,
    )
    stream.cfn_resource = firehose.DeliveryStream(stream.logical_name, **props)
    set_replace_iam_role(stream)
    stream.init_outputs()
    stream.generate_outputs()


def create_streams_template(new_resources, settings):
    """
    Function to create the root template for Kinesis streams

    :param list<DeliveryStream> new_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    root_template = build_template("Root stack for ecs_composex.kinesis_firehose")
    for res in new_resources:
        res.iam_linked_role = IamRole(
            f"{res.logical_name}IamRole",
            AssumeRolePolicyDocument=service_role_trust_policy("firehose"),
            Description=Sub(
                f"Firehose IAM Role for {res.logical_name} - ${{STACK_NAME}}",
                STACK_NAME=define_stack_name(root_template),
            ),
        )
        create_new_stream(res)
        root_template.add_resource(res.cfn_resource)
        root_template.add_resource(res.iam_linked_role)
        root_template.add_output(res.outputs)
    return root_template
