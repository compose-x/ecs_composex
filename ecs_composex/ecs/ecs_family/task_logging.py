#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from itertools import chain

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub
from troposphere.iam import Policy, PolicyType
from troposphere.logs import LogGroup

from ecs_composex.common import LOG
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.compose.compose_services.helpers import set_logging_expiry
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T, LOG_GROUP_RETENTION, LOG_GROUP_T

LOGGING_ACTIONS = ["logs:CreateLogStream", "logs:PutLogEvents"]


def create_log_group(family: ComposeFamily) -> None:
    """
    Function to create a new Log Group for the services
    :return:
    """
    svc_log = family.template.add_resource(
        LogGroup(
            LOG_GROUP_T,
            RetentionInDays=Ref(LOG_GROUP_RETENTION),
            LogGroupName=Sub(
                f"${{STACK_NAME}}/"
                f"svc/ecs/${{{CLUSTER_NAME_T}}}/{family.logical_name}",
                STACK_NAME=define_stack_name(
                    family.template if family.template else None
                ),
            ),
        ),
    )
    policy = PolicyType(
        f"{family.logical_name}LogGroupAccess",
        PolicyName=Sub(f"CloudWatchAccessForFamily{family.logical_name}"),
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                    "Effect": "Allow",
                    "Action": LOGGING_ACTIONS,
                    "Resource": [GetAtt(svc_log, "Arn")],
                }
            ],
        },
        Roles=[family.iam_manager.exec_role.name],
    )
    if (
        family.template
        and f"{family.logical_name}LogGroupAccess" not in family.template.resources
    ):
        family.template.add_resource(policy)


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
                        "Action": LOGGING_ACTIONS + ["logs:CreateLogGroup"],
                        "Resource": "*",
                    }
                ],
            },
        )
    )


def handle_logging(family: ComposeFamily):
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
