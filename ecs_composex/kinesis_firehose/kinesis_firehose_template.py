# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template
    from .kinesis_firehose_stack import DeliveryStream

from troposphere import NoValue, Sub
from troposphere.firehose import DeliveryStream as CfnDeliveryStream
from troposphere.logs import LogGroup

from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.common.logging import LOG
from ecs_composex.resources_import import (
    get_dest_resource_nested_property,
    import_record_properties,
)

from ..common.troposphere_tools import add_outputs, add_resource, build_template
from .kinesis_firehose_iam_helpers import set_replace_iam_role
from .kinesis_firehose_logging_helpers import (
    grant_log_group_access,
    set_replace_cw_logging,
)


def values_validation(stream: DeliveryStream) -> None:
    """
    Simple function to do values validation based on errors / limits encountered
    """

    properties_to_values_mapping = {
        "ExtendedS3DestinationConfiguration::BufferingHints::IntervalInSeconds": ">= 60",
        "ExtendedS3DestinationConfiguration::BufferingHints::SizeInMBs": ">= 64",
    }
    for property_path, expression in properties_to_values_mapping.items():
        prop_attr = get_dest_resource_nested_property(
            property_path, stream.cfn_resource
        )
        if not prop_attr:
            continue
        value = getattr(prop_attr[0], prop_attr[1])
        if not isinstance(value, (str, int, float)):
            LOG.debug(
                f"{stream.name} - Not evaluating property {prop_attr[1]} - {type(value)}"
            )
            continue
        if isinstance(expression, str):
            eval_str = f"{value} {expression}"
            if not eval(eval_str):
                raise ValueError(
                    stream.module.res_key,
                    stream.name,
                    "Property",
                    property_path.replace(r"::", r"."),
                    "is invalid",
                    value,
                    "must be",
                    expression,
                )
        elif callable(expression):
            expression(stream, prop_attr)


def create_new_stream(stream: DeliveryStream) -> None:
    """
    Imports the settings from CFN Definitions and define the CFN Resource from properties

    :param DeliveryStream stream:
    """
    props = import_record_properties(
        stream.properties,
        CfnDeliveryStream,
        ignore_missing_required=True,
        ignore_missing_sub_required=True,
    )
    stream.cfn_resource = CfnDeliveryStream(stream.logical_name, **props)
    stream.log_group = LogGroup(
        f"{stream.logical_name}LogGroup",
        LogGroupName=Sub(
            f"firehose/${{STACK_ID}}/{stream.name}", STACK_ID=STACK_ID_SHORT
        ),
    )
    if (
        stream.cfn_resource.DeliveryStreamType == "KinesisStreamAsSource"
        and stream.cfn_resource.DeliveryStreamEncryptionConfigurationInput != NoValue
    ):
        LOG.error(
            f"{stream.module.res_key}.{stream.name} -"
            " You can only have ServerSide encryption with DirectPut DeliveryStream. Removing."
        )
        stream.cfn_resource.DeliveryStreamEncryptionConfigurationInput = NoValue
    set_replace_iam_role(stream)
    values_validation(stream)
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
        add_resource(root_template, res.cfn_resource)
        add_resource(root_template, res.iam_manager.service_linked_role)
        add_resource(root_template, res.log_group)
        add_resource(root_template, grant_log_group_access(res))
        set_replace_cw_logging(res, root_template)
        add_outputs(root_template, res.outputs)
        res.ensure_iam_policies_dependencies()
    return root_template
