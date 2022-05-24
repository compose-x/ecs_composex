#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService

from itertools import chain

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import GetAtt, NoValue, Ref, Region, Sub
from troposphere.ecs import LogConfiguration
from troposphere.iam import Policy
from troposphere.logs import LogGroup

from ecs_composex.common import LOG, add_resource
from ecs_composex.compose.compose_services.logging_definition_helpers import (
    handle_managed_log_drivers,
)
from ecs_composex.ecs.ecs_params import LOG_GROUP_RETENTION, LOG_GROUP_T
from ecs_composex.resource_settings import define_iam_permissions

LOGGING_ACTIONS = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:CreateLogGroup"]
LOGGING_IAM_PERMISSIONS_MODEL: dict = {"Effect": "Allow", "Action": LOGGING_ACTIONS}


def create_log_group(
    family: ComposeFamily,
    grant_task_role_access: bool = False,
) -> LogGroup:
    """
    Function to create a new Log Group for the services
    :return:
    """
    if LOG_GROUP_T not in family.template.resources:
        svc_log = LogGroup(
            LOG_GROUP_T,
            RetentionInDays=Ref(LOG_GROUP_RETENTION),
            LogGroupName=family.logging_group_name,
        )
        add_resource(family.template, svc_log)

    else:
        svc_log = family.template.resources[LOG_GROUP_T]
    roles = [family.iam_manager.exec_role.name]
    if grant_task_role_access:
        roles.append(family.iam_manager.task_role.name)
    define_iam_permissions(
        "logs",
        family,
        family.template,
        "CloudWatchLogsAccess",
        LOGGING_IAM_PERMISSIONS_MODEL,
        access_definition="LogGroupOwner",
        resource_arns=[GetAtt(svc_log, "Arn")],
        roles=roles,
    )

    return svc_log


def add_container_level_log_group(
    family: ComposeFamily,
    service,
    log_group_access_sid: str,
    grant_task_role_access: bool = False,
):
    """
    Method to add a new log group for a specific container/service defined when awslogs-group has been set.

    :param family:
    :param service:
    :param str log_group_access_sid:
    :param bool grant_task_role_access:
    """

    roles = [family.iam_manager.exec_role.name]
    if grant_task_role_access:
        roles.append(family.iam_manager.task_role.name)
    define_iam_permissions(
        "logs",
        family,
        family.template,
        "CloudWatchLogsAccess",
        LOGGING_IAM_PERMISSIONS_MODEL,
        access_definition="LogGroupOwner",
        resource_arns=[
            Sub(
                "arn:${AWS::Partition}:logs:*:${AWS::AccountId}:log-group:"
                f"{service.logging.Options['awslogs-group']}:*"
            )
        ],
        roles=roles,
        sid_override=log_group_access_sid,
    )
    service.logging.Options.update({"awslogs-create-group": True})


def logging_from_defined_region(family: ComposeFamily, service: ComposeService) -> None:
    """
    If the region for a log group is given, we just take the shortcut to granting all access
    to logs in all regions, for any log group / stream.

    :param family:
    :param service:
    :return:
    """
    LOG.warning(
        f"{family.name}.logging.awslogs driver "
        "- When defining awslogs-region, Compose-X does not create the CW Log Group"
    )
    family.iam_manager.exec_role.cfn_resource.Policies.append(
        Policy(
            PolicyName=f"CloudWatchAccessFor{family.logical_name}",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                        "Effect": "Allow",
                        "Action": LOGGING_ACTIONS,
                        "Resource": Sub(
                            "arn:${AWS::Partition}:logs:*:${AWS::AccountId}:log-group:*"
                        ),
                    }
                ],
            },
        )
    )
    service.logging.Options.update({"awslogs-create-group": True})


def handle_awslogs_logging(family: ComposeFamily):
    """
    Method to go over each service logging configuration and accordingly define the IAM permissions needed for
    the exec role

    If the region was passed in the log driver options, just grant access to any lo group
    ElIf the group name is set and is a string, passed by the log driver options, just grant access to it.
    """
    if not family.template:
        raise AttributeError(
            family.name,
            "Template not yet initialized. Must have a valid template to configure logging",
        )

    for service in chain(family.managed_sidecars, family.ordered_services):
        if keyisset("awslogs-region", service.logging.Options) and isinstance(
            service.logging.Options["awslogs-region"], str
        ):
            logging_from_defined_region(family, service)
        elif keyisset("awslogs-group", service.logging.Options) and not isinstance(
            service.logging.Options["awslogs-group"], (Ref, Sub)
        ):
            add_container_level_log_group(
                family, service, f"{service.logical_name}LogGroupAccess"
            )
        else:
            service.logging.Options.update(
                {"awslogs-group": Ref(family.umbrella_log_group)}
            )


def handle_firelens(family: ComposeFamily, settings: ComposeXSettings) -> None:
    """
    Handles the firelens configuration / creation for the services
    """
    from ecs_composex.ecs.ecs_firelens.firelens_managed_sidecars import (
        FLUENT_BIT_AGENT_NAME,
        FluentBit,
        render_agent_config,
    )

    family_fluentbit_service = FluentBit(
        FLUENT_BIT_AGENT_NAME, render_agent_config(family)
    )
    family_fluentbit_service.set_firelens_configuration()
    family_fluentbit_service.add_to_family(family, True)
    family_fluentbit_service.set_as_dependency_to_family_services()
    family_fluentbit_service.update_family_services_logging_configuration(settings)
    setattr(
        family_fluentbit_service.container_definition,
        "LogConfiguration",
        LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Ref(family.umbrella_log_group),
                "awslogs-region": Region,
                "awslogs-stream-prefix": family_fluentbit_service.name,
            },
        ),
    )


def init_verify_services_log_configuration(family: ComposeFamily) -> None:
    default_family_options = {
        "awslogs-group": Ref(family.umbrella_log_group),
        "awslogs-region": Region,
    }
    for service in chain(family.managed_sidecars, family.ordered_services):
        svc_logging_def = set_else_none("logging", service.definition)
        svc_logging_driver = set_else_none("driver", svc_logging_def)
        if svc_logging_driver in ["awslogs", "awsfirelens"]:

            log_config = handle_managed_log_drivers(
                service, svc_logging_driver, svc_logging_def, family.umbrella_log_group
            )
        else:
            default_family_options.update({"awslogs-stream-prefix": service.name})
            log_config = LogConfiguration(
                LogDriver="awslogs", Options=default_family_options
            )

        service.logging = log_config
        setattr(service.container_definition, "LogConfiguration", service.logging)


def handle_logging(family: ComposeFamily, settings: ComposeXSettings) -> None:
    """
    Configuration parser to catch firelens vs aws cloudwatch config

    :param ComposeFamily family:
    :param ComposeXSettings settings:
    """
    wants_firelens = any(
        [service.x_logging_firelens for service in family.ordered_services]
    )
    if not wants_firelens:
        family.umbrella_log_group = create_log_group(family)
        init_verify_services_log_configuration(family)
        handle_awslogs_logging(family)
    else:
        LOG.info(
            f"{family.name} - At least one service has x-logging.FireLens set. Overriding for all."
        )
        family.umbrella_log_group = create_log_group(family, True)
        init_verify_services_log_configuration(family)
        handle_firelens(family, settings)
