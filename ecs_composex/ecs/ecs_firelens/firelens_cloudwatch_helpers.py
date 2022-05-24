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
from troposphere import Ref, Region, Sub
from troposphere.iam import PolicyType

from ecs_composex.common import LOG, add_resource
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.ecs.ecs_family.task_logging import (
    LOGGING_IAM_PERMISSIONS_MODEL,
    create_log_group,
)
from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream
from ecs_composex.resource_settings import define_iam_permissions


def set_default_cloudwatch_logging_options(
    family: ComposeFamily,
    service: ComposeService,
    options: dict,
    settings: ComposeXSettings,
) -> None:
    """
    Sets up all the options for CloudWatch in absence of fluentbit options

    :param family:
    :param service:

    :param options:
    :param settings:
    """
    log_group_resource = create_log_group(family, grant_task_role_access=True)
    options.update(
        {
            "Name": "cloudwatch",
            "region": Region,
            "auto_create_group": True,
            "log_group_name": Ref(log_group_resource),
            "log_stream_prefix": service.service_name,
        }
    )


def handle_cloudwatch_log_group_name(
    family: ComposeFamily,
    service: ComposeService,
    log_config: LogConfiguration,
    parameter_name: str,
    options: dict,
    settings: ComposeXSettings,
):
    """
    Function to handle Log Group settings and permissions for CloudWatch FireLens settings

    :param family:
    :param service:
    :param log_config:
    :param parameter_name:
    :param options:
    :param settings:
    """
    if not isinstance(options[parameter_name], str):
        return options[parameter_name]
    _arn = Sub(
        f"arn:${{AWS::Partition}}:logs:*:${{AWS::AccountId}}:log-group:{options[parameter_name]}:*"
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
    return options[parameter_name]
