#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to add Prometheus scraper for ECS tasks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.managed_sidecars import ManagedSidecar
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from troposphere.ssm import Parameter

from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, Sub
from troposphere.ecs import Secret
from troposphere.iam import PolicyType

from ecs_composex.common.troposphere_tools import add_resource
from ecs_composex.ecs import ecs_params


def define_cloudwatch_agent(cw_prometheus_config, cw_agent_config) -> ManagedSidecar:
    """
    Function to define the CW Agent image task definition

    :param cw_prometheus_config:
    :param cw_agent_config:
    :return:
    """
    from copy import deepcopy

    from ecs_composex.ecs.managed_sidecars.aws_cw_agent import CW_AGENT_SERVICE

    cw_service = deepcopy(CW_AGENT_SERVICE)
    secrets = [
        Secret(
            Name="CW_CONFIG_CONTENT",
            ValueFrom=Sub(
                f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                f":parameter${{{cw_agent_config.title}}}"
            ),
        ),
    ]
    if cw_prometheus_config:
        secrets.append(
            Secret(
                Name="PROMETHEUS_CONFIG_CONTENT",
                ValueFrom=Sub(
                    f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                    f":parameter${{{cw_prometheus_config.title}}}"
                ),
            ),
        )
    if hasattr(cw_service.container_definition, "Secrets"):
        s_secrets = getattr(cw_service.container_definition, "Secrets")
        if isinstance(s_secrets, list):
            s_secrets += secrets
        else:
            setattr(cw_service.container_definition, "Secrets", secrets)
    else:
        setattr(cw_service.container_definition, "Secrets", secrets)
    return cw_service


def set_ecs_cw_policy(
    family: ComposeFamily,
    prometheus_parameter: Parameter,
    cw_config_parameter: Parameter,
) -> None:
    """
    Renders the IAM policy to grant the TaskRole access to CW, ECS and SSM Parameters

    :param family: The Service family
    :param troposphere.ssm.Parameter prometheus_parameter:
    :param troposphere.ssm.Parameter cw_config_parameter:
    """
    ecs_sd_policy = PolicyType(
        "CWAgentAccessForEcsScraping",
        PolicyName="CWAgentAccessForEcsScraping",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EnableCreationAndManagementOfContainerInsightsLogEvents",
                    "Effect": "Allow",
                    "Action": ["logs:GetLogEvents", "logs:PutLogEvents"],
                    "Resource": Sub(
                        f"arn:${{{AWS_PARTITION}}}:logs:*:${{{AWS_ACCOUNT_ID}}}:"
                        "log-group:/aws/ecs/containerinsights/*:log-stream:*"
                    ),
                },
                {
                    "Sid": "EnableCreationAndManagementOfContainerInsightsCloudwatchLogGroupsAndStreams",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:DescribeLogStreams",
                        "logs:PutRetentionPolicy",
                        "logs:CreateLogGroup",
                    ],
                    "Resource": Sub(
                        f"arn:${{{AWS_PARTITION}}}:logs:*:${{{AWS_ACCOUNT_ID}}}:"
                        "log-group:/aws/ecs/containerinsights/*"
                    ),
                },
                {
                    "Sid": "ECSTaskDefinitionsAccess",
                    "Effect": "Allow",
                    "Action": ["ecs:DescribeTaskDefinition"],
                    "Resource": "*",
                },
                {
                    "Sid": "ServiceDiscoveryAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecs:DescribeTasks",
                        "ecs:ListTasks",
                        "ecs:DescribeContainerInstances",
                        "ecs:DescribeServices",
                        "ecs:ListServices",
                    ],
                    "Resource": "*",
                    "Condition": {
                        "ArnEquals": {
                            "ecs:cluster": Sub(
                                f"arn:${{{AWS_PARTITION}}}:ecs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                                f":cluster/${{{ecs_params.CLUSTER_NAME.title}}}"
                            )
                        }
                    },
                },
            ],
        },
        Roles=[
            family.iam_manager.exec_role.name,
            family.iam_manager.task_role.name,
        ],
    )
    if prometheus_parameter:
        ecs_sd_policy.PolicyDocument["Statement"].append(
            {
                "Sid": "ExtractFromCloudWatchAgentServerPolicy",
                "Effect": "Allow",
                "Action": ["ssm:GetParameter*"],
                "Resource": [
                    Sub("arn:aws:ssm:*:${AWS::AccountId}:parameter/AmazonCloudWatch-*"),
                    Sub(
                        f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                        f":parameter${{{prometheus_parameter.title}}}"
                    ),
                    Sub(
                        f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                        f":parameter${{{cw_config_parameter.title}}}"
                    ),
                ],
            },
        )
    add_resource(family.template, ecs_sd_policy)
