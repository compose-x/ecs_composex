#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere.ecs import LogConfiguration
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService
    from ecs_composex.common.settings import ComposeXSettings

from compose_x_common.aws import validate_iam_role_arn
from troposphere import Sub
from troposphere.iam import PolicyType

from ecs_composex.common import LOG, add_resource
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream


def handle_x_kinesis_firehose(
    family: ComposeFamily,
    service: ComposeService,
    log_config: LogConfiguration,
    parameter_name: str,
    config_value: str,
    settings: ComposeXSettings,
):
    """
    Detects if delivery_stream is x-kinesis_firehose and interpolates the stream name

    :param family:
    :param service:
    :param log_config:
    :param parameter_name:
    :param config_value:
    :param settings:
    :return: The pointer to kinesis stream
    """
    if not config_value.startswith("x-kinesis_firehose::"):
        return config_value
    delivery_stream_name = config_value.replace("x-kinesis_firehose::", "")
    for resource in settings.x_resources:
        if not isinstance(resource, DeliveryStream) or not issubclass(
            type(resource), DeliveryStream
        ):
            continue
        if resource.name == delivery_stream_name:
            break
    else:
        raise LookupError(
            f"{family.name}.{service.name} - {delivery_stream_name} not found in x-kinesis_firehose"
        )
    for target in resource.families_targets:
        if target[0] == family:
            LOG.info(
                f"{family.name}.{service.name} is already a target of {resource.module.res_key}.{resource.name}"
            )
            break
    else:
        LOG.info(
            f"{family.name}.{service.name} - adding as target to {resource.module.res_key}.{resource.name}"
        )
        family_target = (family, True, family.services, {"Producer"})
        resource.families_targets.append(family_target)
        resource.to_ecs(settings, None, None, targets_overrides=[family_target])
