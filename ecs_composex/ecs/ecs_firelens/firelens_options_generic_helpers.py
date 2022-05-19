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
from troposphere import Sub
from troposphere.iam import PolicyType

from ecs_composex.common import LOG, add_resource
from ecs_composex.common.cfn_params import STACK_ID_SHORT


def handle_cross_account_permissions(
    family: ComposeFamily,
    service: ComposeService,
    log_config: LogConfiguration,
    parameter_name: str,
    config_value: str,
    settings: ComposeXSettings,
):
    """
    Function to automatically add cross-account role access for FireHose to the specified role ARN
    :param family:
    :param service:
    :param log_config:
    :param parameter_name:
    :param config_value:
    :return:
    """
    try:
        arn = validate_iam_role_arn(config_value)
    except ValueError:
        LOG.error(
            f"{family.name}.{service.name} - FireLens config for firehose role_arn is invalid"
        )
        raise
    policy_title = (
        f"{family.logical_name}{service.logical_name}LoggingFirehoseCrossAccount"
    )
    if policy_title in family.template.resources:
        policy = family.template.resources[policy_title]
        resource = policy.PolicyDocument["Statement"][0]["Resource"]
        if isinstance(resource, str):
            resource = [resource]
        if arn not in resource:
            policy.PolicyDocument["Statement"][0]["Resource"].append(arn)
    else:
        policy = PolicyType(
            policy_title,
            PolicyName=Sub(
                f"{family.logical_name}{service.logical_name}FireHoseCrossAccountAccess${{STACK_ID}}",
                STACK_ID=STACK_ID_SHORT,
            ),
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "LoggingFirehoseCrossAccount",
                        "Effect": "Allow",
                        "Action": ["sts:AssumeRole"],
                        "Resource": [arn],
                    }
                ],
            },
            Roles=family.iam_manager.task_role.name,
        )
        add_resource(family.template, policy)
    return arn
