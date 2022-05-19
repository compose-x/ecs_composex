#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import ComposeService

from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from troposphere import NoValue, Region
from troposphere.ecs import LogConfiguration


def handle_awslogs_options(
    service: ComposeService, logging_def: dict
) -> LogConfiguration:
    options_def = logging_def["options"]
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


def handle_firelens_options(
    service: ComposeService, logging_def: dict, set_cw_default: bool = False
) -> LogConfiguration:
    default_cloudwatch_options = {
        "Name": "cloudwatch",
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
    return LogConfiguration(LogDriver="awsfirelens", Options=options)
