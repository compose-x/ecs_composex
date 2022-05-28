#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from os import path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from troposphere.ecs import LogConfiguration
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import keyisset, set_else_none

from ecs_composex.common import LOG, add_resource
from ecs_composex.ssm_parameter.ssm_parameter_stack import SsmParameter

from .firelens_cloudwatch_helpers import (
    handle_cloudwatch_log_group_name,
    set_default_cloudwatch_logging_options,
)
from .firelens_firehose_helpers import handle_x_kinesis_firehose
from .firelens_options_generic_helpers import handle_cross_account_permissions


def handle_firehose_config(
    family: ComposeFamily,
    service: ComposeService,
    log_config: LogConfiguration,
    options: dict,
    settings: ComposeXSettings,
) -> None:
    """
    Function to handle firehose destination and detect settings to set accordingly, such as IAM Permissions

    :param ComposeFamily family:
    :param ComposeService service:
    :param LogConfiguration log_config:
    :param dict options:
    :param ComposeXSettings settings:
    """

    param_to_handler = {
        "delivery_stream": handle_x_kinesis_firehose,
        "role_arn": handle_cross_account_permissions,
    }
    for param_name, param_function in param_to_handler.items():
        if param_name in options.keys() and param_function:
            options[param_name] = param_function(
                family, service, log_config, param_name, options[param_name], settings
            )


def handle_cloudwatch(
    family: ComposeFamily,
    service: ComposeService,
    log_config: LogConfiguration,
    options: dict,
    settings: ComposeXSettings,
) -> None:
    """
    Handles cloudwatch settings and IAM. Some parameters can not be set and we will auto-define values for these as
    a backup.

    :param ComposeFamily family:
    :param ComposeService service:
    :param LogConfiguration log_config:
    :param dict options:
    :param ComposeXSettings settings:
    """
    param_to_handler = {
        "log_group_name": (
            handle_cloudwatch_log_group_name,
            set_default_cloudwatch_logging_options,
        ),
        "role_arn": (handle_cross_account_permissions, None),
        "log_retention_days": (None, 30),
    }
    for param_name, param_function in param_to_handler.items():
        if param_name in options.keys() and param_function[0]:
            options[param_name] = param_function[0](
                family, service, log_config, param_name, options, settings
            )
        elif param_name in options.keys() and param_function[1]:
            if isinstance(param_function[1], (str, int, float)) or not callable(
                param_function[1]
            ):
                options[param_name] = param_function[1]
            else:
                param_function[1](family, service, options, settings)
        else:
            if callable(param_function[1]):
                param_function[1](family, service, options, settings)


def parse_set_update_firelens_configuration_options(
    family: ComposeFamily,
    service: ComposeService,
    log_config: LogConfiguration,
    settings: ComposeXSettings,
) -> None:
    """
    Parses the defined options for awsfirelens "driver" and set other settings based on that.

    :param ComposeFamily family:
    :param ComposeService service:
    :param LogConfiguration log_config:
    :param ComposeXSettings settings:
    """
    options = getattr(log_config, "Options") if hasattr(log_config, "Options") else None
    if not options:
        return
    if options and log_config.LogDriver == "awsfirelens":
        name = set_else_none("Name", options)
        if not name and not family.firelens_service:
            raise KeyError(
                family.name,
                service.name,
                "logging.Options does not define a Name for firelens and no advanced configuration defined",
            )
        elif name == "firehose" or name == "kinesis_firehose":
            handle_firehose_config(family, service, log_config, options, settings)
        elif name == "cloudwatch":
            handle_cloudwatch(family, service, log_config, options, settings)


def handle_s3_configuration(family: ComposeFamily, settings: ComposeXSettings) -> None:
    """
    Handles x-logging.FireLens.Advanced.s3FileConfiguration

    :param family:
    :param settings:
    """


def update_set_fluent_configuration_from_advanced(
    family: ComposeFamily, settings: ComposeXSettings
):
    """

    :param family:
    :param settings:
    :return:
    """
    advanced_settings = set_else_none(
        "Advanced", family.firelens_advanced_reference_service.x_logging_firelens
    )
    print("AVANCED ?", advanced_settings)
    if not advanced_settings:
        return
    if keyisset("Rendered", advanced_settings):
        from .firelens_advanced_rendered_settings import handle_rendered_settings

        handle_rendered_settings(family, settings, advanced_settings["Rendered"])
    elif keyisset("s3FileConfiguration", advanced_settings):
        handle_s3_configuration(family, settings)
