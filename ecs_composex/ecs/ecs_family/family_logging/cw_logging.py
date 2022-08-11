#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService

from troposphere import GetAtt, Ref, Sub
from troposphere.iam import Policy
from troposphere.logs import LogGroup

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_resource
from ecs_composex.ecs.ecs_params import LOG_GROUP_RETENTION, LOG_GROUP_T
from ecs_composex.resource_settings import define_iam_permissions

LOGGING_ACTIONS = [
    "logs:CreateLogStream",
    "logs:PutLogEvents",
    "logs:CreateLogGroup",
    "logs:Describe*",
]
LOGGING_IAM_PERMISSIONS_MODEL: dict = {"Effect": "Allow", "Action": LOGGING_ACTIONS}


def create_log_group(
    family: ComposeFamily,
    group_name,
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
            LogGroupName=group_name,
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
                f"{service.logging.log_options['awslogs-group']}:*"
            )
        ],
        roles=roles,
        sid_override=log_group_access_sid,
    )
    service.logging.log_options.update({"awslogs-create-group": True})


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
    service.logging.log_options.update({"awslogs-create-group": True})
