#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import set_else_none

from ecs_composex.ecs.ecs_firelens.helpers.cloudwatch_helpers import (
    handle_cloudwatch_log_group_name,
    set_default_cloudwatch_logging_options,
)
from ecs_composex.ecs.ecs_firelens.helpers.firehose_helpers import (
    handle_x_kinesis_firehose,
)
from ecs_composex.ecs.ecs_firelens.helpers.kinesis_helpers import handle_x_kinesis

from .firelens_options_generic_helpers import handle_cross_account_permissions


def handle_firehose_config(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
) -> None:
    """
    Function to handle firehose destination and detect settings to set accordingly, such as IAM Permissions

    :param ComposeFamily family:
    :param ComposeService service:
    :param ComposeXSettings settings:
    """

    param_to_handler = {
        "delivery_stream": handle_x_kinesis_firehose,
        "role_arn": handle_cross_account_permissions,
    }
    for param_name, param_function in param_to_handler.items():
        if param_name in service.logging.log_options.keys() and param_function:
            service.logging.log_options[param_name] = param_function(
                family,
                service,
                settings,
                param_name,
                service.logging.log_options[param_name],
            )


def handle_kinesis_config(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
) -> None:
    """
    Function to handle kinesis datastream destination and detect settings to set accordingly, such as IAM Permissions

    :param ComposeFamily family:
    :param ComposeService service:
    :param ComposeXSettings settings:
    """

    param_to_handler = {
        "delivery_stream": handle_x_kinesis,
        "role_arn": handle_cross_account_permissions,
    }
    for param_name, param_function in param_to_handler.items():
        if param_name in service.logging.log_options.keys() and param_function:
            service.logging.log_options[param_name] = param_function(
                family,
                service,
                settings,
                param_name,
                service.logging.log_options[param_name],
            )


def handle_cloudwatch(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
) -> None:
    """
    Handles cloudwatch settings and IAM. Some parameters can not be set and we will auto-define values for these as
    a backup.

    :param ComposeFamily family:
    :param ComposeService service:
    :param ComposeXSettings settings:
    """
    param_to_handler = {
        "log_group_name": (
            handle_cloudwatch_log_group_name,
            set_default_cloudwatch_logging_options,
        ),
        "role_arn": (handle_cross_account_permissions, None),
        "log_retention_days": (None, service.logging.cw_retention_period),
    }
    for param_name, param_function in param_to_handler.items():
        if (
            param_name in service.logging.log_options.keys()
            and param_function[0]
            and callable(param_function[0])
        ):
            service.logging.log_options[param_name] = param_function[0](
                family,
                service,
                settings,
                param_name,
            )
        elif param_name in service.logging.log_options.keys() and param_function[1]:
            if isinstance(param_function[1], (str, int, float)) or not callable(
                param_function[1]
            ):
                service.logging.log_options[param_name] = param_function[1]
            else:
                param_function[1](family, service, settings)
        else:
            if callable(param_function[1]):
                param_function[1](family, service, settings)


def parse_set_update_firelens_configuration_options(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
) -> None:
    """
    Parses the defined options for awsfirelens "driver" and set other settings based on that.

    :param ComposeFamily family:
    :param ComposeService service:
    :param ComposeXSettings settings:
    """
    if service.logging.log_driver == "awsfirelens" and service.logging.log_options:
        name = set_else_none("Name", service.logging.log_options)
        if not name:
            raise ValueError(
                service.name,
                "No Name set for awsfirelens options",
                service.logging.log_options,
            )
        if name == "firehose" or name == "kinesis_firehose":
            handle_firehose_config(family, service, settings)
        elif name == "cloudwatch":
            handle_cloudwatch(family, service, settings)
        elif name == "kinesis" or name == "kinesis_streams":
            handle_kinesis_config(family, service, settings)
