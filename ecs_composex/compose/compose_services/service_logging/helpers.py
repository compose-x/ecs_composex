#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from troposphere import NoValue, Ref, Region
from troposphere.ecs import LogConfiguration

from ecs_composex.ecs.ecs_params import LOG_GROUP_RETENTION


def handle_awslogs_options(
    service: ComposeService, logging_def: dict
) -> LogConfiguration:
    options_def = set_else_none("options", logging_def)
    options = {
        "awslogs-group": set_else_none(
            "awslogs-group", options_def, alt_value=service.logical_name
        ),
        "awslogs-region": set_else_none(
            "awslogs-region", options_def, alt_value=Region
        ),
        "awslogs-stream-prefix": set_else_none(
            "awslogs-stream-prefix", options_def, alt_value=service.name
        ),
        "awslogs-endpoint": set_else_none(
            "awslogs-endpoint", options_def, alt_value=NoValue
        ),
        "awslogs-datetime-format": set_else_none(
            "awslogs-datetime-format",
            options_def,
            alt_value=NoValue,
        ),
        "awslogs-multiline-pattern": set_else_none(
            "awslogs-multiline-pattern",
            options_def,
            alt_value=NoValue,
        ),
        "mode": set_else_none("mode", options_def, alt_value=NoValue),
        "max-buffer-size": set_else_none(
            "max-buffer-size", options_def, alt_value=NoValue
        ),
    }
    if keypresent("awslogs-create-group", options_def) and isinstance(
        options_def["awslogs-create-group"], bool
    ):
        options["awslogs-create-group"] = keyisset("awslogs-create-group", options_def)
    elif keypresent("awslogs-create-group", options_def) and isinstance(
        options_def["awslogs-create-group"], str
    ):
        options["awslogs-create-group"] = options_def["awslogs-create-group"] in [
            "yes",
            "true",
            "Yes",
            "True",
        ]
    return LogConfiguration(
        LogDriver="awslogs",
        Options=options,
    )


def replace_awslogs_with_firelens_configuration(
    service: ComposeService, awslogs_config: LogConfiguration
) -> LogConfiguration:
    """
    Remaps the awslogs driver options into the fluentbit options

    :param ComposeService service:
    :param LogConfiguration awslogs_config:
    :return:
    """
    awslogs_to_fluentbit = {
        "awslogs-group": "log_group_name",
        "awslogs-stream-prefix": "log_stream_prefix",
        "awslogs-endpoint": "endpoint",
        "awslogs-region": "region",
        "awslogs-create-group": "auto_create_group",
    }
    set_options = awslogs_config.Options
    fluent_bit_options: dict = {"Name": "cloudwatch"}
    for awslogs_option, fluentbit_option in awslogs_to_fluentbit.items():
        if keyisset(awslogs_option, set_options):
            if (
                isinstance(set_options[awslogs_option], Ref)
                and set_options[awslogs_option] == NoValue
            ):
                continue
            elif set_options[awslogs_option]:
                fluent_bit_options[fluentbit_option] = set_options[awslogs_option]
    if not keyisset("log_group_name", fluent_bit_options):
        fluent_bit_options["log_group_name"] = f"ecs/svc/{service.logical_name}"
    if not keyisset("log_stream_prefix", fluent_bit_options):
        fluent_bit_options["log_stream_prefix"] = service.name
    if not keypresent("auto_create_group", fluent_bit_options):
        fluent_bit_options["auto_create_group"] = True
    return LogConfiguration(LogDriver="awsfirelens", Options=fluent_bit_options)


def handle_firelens_options(
    service: ComposeService, logging_def: dict, set_cw_default: bool = False
) -> LogConfiguration:
    default_cloudwatch_options = {
        "region": Region,
        "auto_create_group": True,
        "log_group_name": service.logical_name,
        "log_stream_prefix": service.service_name,
    }
    if set_cw_default:
        options = set_else_none(
            "options", logging_def, alt_value=default_cloudwatch_options
        )
    else:
        options = set_else_none("options", logging_def, alt_value=NoValue)
    config_name_map = {
        "delivery_stream": "kinesis_firehose",
        "log_group_name": "cloudwatch",
        "stream": "kinesis_streams",
        "bucket": "s3",
    }
    for key, value in config_name_map.items():
        if keyisset(key, options):
            options.update({"Name": value})
            if not keyisset("region", options):
                options.update({"region": Region})
            break

    return LogConfiguration(LogDriver="awsfirelens", Options=options)


def get_closest_valid_log_retention_period(set_expiry):
    return min(
        LOG_GROUP_RETENTION.AllowedValues,
        key=lambda x: abs(x - max([set_expiry])),
    )
