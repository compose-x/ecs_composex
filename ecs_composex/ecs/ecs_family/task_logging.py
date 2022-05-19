#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily

from itertools import chain

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub
from troposphere.iam import Policy, PolicyType
from troposphere.logs import LogGroup

from ecs_composex.common import LOG, add_resource
from ecs_composex.compose.compose_services.helpers import set_logging_expiry
from ecs_composex.ecs.ecs_params import LOG_GROUP_RETENTION, LOG_GROUP_T
from ecs_composex.resource_settings import define_iam_permissions

LOGGING_ACTIONS = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:CreateLogGroup"]


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
    permissions_model = {"Effect": "Allow", "Action": LOGGING_ACTIONS}
    roles = [family.iam_manager.exec_role.name]
    if grant_task_role_access:
        roles.append(family.iam_manager.task_role.name)
    define_iam_permissions(
        "logs",
        family,
        family.template,
        "CloudWatchLogsAccess",
        permissions_model,
        access_definition="LogGroupOwner",
        resource_arns=[GetAtt(svc_log, "Arn")],
        roles=roles,
    )

    return svc_log


def add_container_level_log_group(
    family: ComposeFamily, service, log_group_title, expiry
):
    """
    Method to add a new log group for a specific container/service defined when awslogs-group has been set.

    :param family:
    :param service:
    :param str log_group_title:
    :param expiry:
    """
    if log_group_title not in family.template.resources:
        log_group = family.template.add_resource(
            LogGroup(
                log_group_title,
                LogGroupName=service.logging.Options["awslogs-group"],
                RetentionInDays=expiry,
            )
        )
        policy = PolicyType(
            f"CloudWatchAccessFor{family.logical_name}{log_group_title}",
            PolicyName=f"CloudWatchAccessFor{family.logical_name}{log_group_title}",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                        "Effect": "Allow",
                        "Action": LOGGING_ACTIONS,
                        "Resource": GetAtt(log_group, "Arn"),
                    }
                ],
            },
            Roles=[family.iam_manager.exec_role.name],
        )
        if family.template and policy.title not in family.template.resources:
            family.template.add_resource(policy)
        service.logging.Options.update({"awslogs-group": Ref(log_group)})
    else:
        LOG.debug("LOG Group and policy already exist")


def logging_from_defined_region(family: ComposeFamily) -> None:
    LOG.warning(
        f"{family.name}.logging - When defining awslogs-region, Compose-X does not create the CW Log Group"
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
                        "Resource": "*",
                    }
                ],
            },
        )
    )


def handle_awslogs_logging(family: ComposeFamily):
    """
    Method to go over each service logging configuration and accordingly define the IAM permissions needed for
    the exec role
    """
    if not family.template:
        return
    for service in chain(family.managed_sidecars, family.ordered_services):
        expiry = set_logging_expiry(service)
        log_group_title = f"{service.logical_name}LogGroup"
        if keyisset("awslogs-region", service.logging.Options) and not isinstance(
            service.logging.Options["awslogs-region"], Ref
        ):
            logging_from_defined_region(family)
        elif keyisset("awslogs-group", service.logging.Options) and not isinstance(
            service.logging.Options["awslogs-group"], (Ref, Sub)
        ):
            add_container_level_log_group(family, service, log_group_title, expiry)
        else:
            service.logging.Options.update({"awslogs-group": Ref(LOG_GROUP_T)})


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


def handle_logging(family: ComposeFamily, settings: ComposeXSettings) -> None:
    """
    Configuration parser to catch firelens vs aws cloudwatch config

    :param ComposeFamily family:
    :param ComposeXSettings settings:
    """
    wants_firelens = any(
        [
            keyisset("FireLens", service.x_logging)
            for service in family.ordered_services
            if service.x_logging
        ]
    )
    if not wants_firelens:
        create_log_group(family)
        handle_awslogs_logging(family)
    else:
        LOG.info(
            f"{family.name} - At least one service has x-logging.FireLens set. Overriding for all."
        )
        handle_firelens(family, settings)
