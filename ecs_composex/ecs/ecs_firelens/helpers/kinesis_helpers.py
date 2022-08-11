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

from compose_x_common.aws.kinesis import KINESIS_STREAM_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap, Ref, Region

from ecs_composex.common.logging import LOG
from ecs_composex.kinesis.kinesis_params import STREAM_ARN, STREAM_ID
from ecs_composex.kinesis.kinesis_stack import Stream


def set_add_family_to_kinesis(
    resource: Stream, family: ComposeFamily, settings: ComposeXSettings
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


def add_data_stream_for_firelens(
    kinesis_stream: Stream,
    env_vars: dict,
    family: ComposeFamily,
    settings: ComposeXSettings,
):
    if not isinstance(kinesis_stream, Stream):
        raise TypeError("kinesis_stream must be", Stream, "Got", type(kinesis_stream))
    set_add_family_to_kinesis(kinesis_stream, family, settings)
    kinesis_stream.add_parameter_to_family_stack(family, settings, STREAM_ID)
    if kinesis_stream.cfn_resource:
        stream_pointer = Ref(
            kinesis_stream.attributes_outputs[STREAM_ID]["ImportParameter"]
        )
        env_vars.update({kinesis_stream.env_var_prefix: stream_pointer})

    else:
        stream_pointer = kinesis_stream.attributes_outputs[STREAM_ID]["ImportValue"]
        env_vars.update({kinesis_stream.env_var_prefix: stream_pointer})
    return stream_pointer


def handle_x_kinesis(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
    parameter_name: str,
    config_value: str,
):
    """
    Detects if delivery_stream is x-kinesis and interpolates the stream name

    :param family:
    :param service:
    :param parameter_name:
    :param config_value:
    :param settings:
    :return: The pointer to kinesis stream
    """
    if not config_value.startswith("x-kinesis::"):
        return config_value
    data_stream = settings.find_resource(config_value)
    pointer = add_data_stream_for_firelens(data_stream, {}, family, settings)
    if not keyisset("region", service.logging.log_options):
        if isinstance(pointer, Ref):
            service.logging.log_options.update({"region": Region})
        elif isinstance(pointer, FindInMap):
            _arn = data_stream.mappings[STREAM_ARN.title]
            service.logging.log_options.update(
                {"region": KINESIS_STREAM_ARN_RE.match(_arn).group("region")}
            )
    return pointer
