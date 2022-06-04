#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to help with common FireLens + CloudWatch configuration and settings
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import Ref, Region, Sub

from ecs_composex.ecs.ecs_family.family_logging.cw_logging import (
    LOGGING_IAM_PERMISSIONS_MODEL,
)
from ecs_composex.resource_settings import define_iam_permissions


def set_default_cloudwatch_logging_options(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
) -> None:
    """
    Sets up all the options for CloudWatch in absence of fluentbit options

    :param family:
    :param service:
    :param settings:
    """
    service.logging.log_options.update(
        {
            "Name": "cloudwatch",
            "region": Region,
            "auto_create_group": True,
            "log_group_name": Ref(family.logging.family_log_group),
            "log_stream_prefix": service.service_name,
        }
    )


def handle_cloudwatch_log_group_name(
    family: ComposeFamily,
    service: ComposeService,
    settings: ComposeXSettings,
    parameter_name: str,
    config_value: Any = None,
):
    """
    Function to handle Log Group settings and permissions for CloudWatch FireLens settings
    """
    if not isinstance(service.logging.log_options[parameter_name], str):
        return service.logging.log_options[parameter_name]
    _arn = Sub(
        f"arn:${{AWS::Partition}}:logs:*:${{AWS::AccountId}}:log-group:{service.logging.log_options[parameter_name]}:*"
    )

    roles = [family.iam_manager.exec_role.name, family.iam_manager.task_role.name]
    define_iam_permissions(
        "logs",
        family,
        family.template,
        "CloudWatchLogsAccess",
        LOGGING_IAM_PERMISSIONS_MODEL,
        access_definition="LogGroupOwner",
        resource_arns=[_arn],
        roles=roles,
        sid_override=f"{service.logical_name}CloudWatchLogsAccess",
    )
    return service.logging.log_options[parameter_name]
