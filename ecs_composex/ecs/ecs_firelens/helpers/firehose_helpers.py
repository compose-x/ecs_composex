#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to help with common FireLens + FireHose configuration and settings
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService
    from ecs_composex.common.settings import ComposeXSettings

from compose_x_common.aws.kinesis import KINESIS_FIREHOSE_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap, Ref, Region

from ecs_composex.common.logging import LOG
from ecs_composex.kinesis_firehose.kinesis_firehose_params import (
    FIREHOSE_ARN,
    FIREHOSE_ID,
)
from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream


def set_add_family_to_firehose(
    resource: DeliveryStream, family: ComposeFamily, settings: ComposeXSettings
):
    for target in resource.families_targets:
        if target[0] == family:
            LOG.info(
                f"{family.name} is already a target of {resource.module.res_key}.{resource.name}"
            )
            break
    else:
        LOG.info(
            f"{family.name} - adding as target to {resource.module.res_key}.{resource.name}"
        )
        if not resource.attributes_outputs:
            resource.init_outputs()
            resource.generate_outputs()
        family_target = (family, True, family.services, "Producer")
        resource.families_targets.append(family_target)
        resource.to_ecs(
            settings,
            settings.mod_manager,
            settings.root_stack,
            targets_overrides=[family_target],
        )


def add_firehose_delivery_stream_for_firelens(
    firehose_stream: DeliveryStream,
    env_vars: dict,
    family: ComposeFamily,
    settings: ComposeXSettings,
):
    if not isinstance(firehose_stream, DeliveryStream):
        raise TypeError(
            "firehose_stream must be", DeliveryStream, "Got", type(firehose_stream)
        )
    set_add_family_to_firehose(firehose_stream, family, settings)
    firehose_stream.add_parameter_to_family_stack(family, settings, FIREHOSE_ID)
    if firehose_stream.cfn_resource:
        firehose_pointer = Ref(
            firehose_stream.attributes_outputs[FIREHOSE_ID]["ImportParameter"]
        )
        env_vars.update({firehose_stream.env_var_prefix: firehose_pointer})

    else:
        firehose_pointer = firehose_stream.attributes_outputs[FIREHOSE_ID][
            "ImportValue"
        ]
        env_vars.update({firehose_stream.env_var_prefix: firehose_pointer})
    return firehose_pointer


def handle_x_kinesis_firehose(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
    parameter_name: str,
    config_value: str,
):
    """
    Detects if delivery_stream is x-kinesis_firehose and interpolates the stream name

    :param family:
    :param service:
    :param parameter_name:
    :param config_value:
    :param settings:
    :return: The pointer to kinesis stream
    """
    if not config_value.startswith("x-kinesis_firehose::"):
        return config_value
    delivery_stream = settings.find_resource(config_value)
    pointer = add_firehose_delivery_stream_for_firelens(
        delivery_stream, {}, family, settings
    )
    if not keyisset("region", service.logging.log_options):
        if isinstance(pointer, Ref):
            service.logging.log_options.update({"region": Region})
        elif isinstance(pointer, FindInMap):
            _arn = delivery_stream.mappings[FIREHOSE_ARN.title]
            service.logging.log_options.update(
                {"region": KINESIS_FIREHOSE_ARN_RE.match(_arn).group("region")}
            )
    return pointer
