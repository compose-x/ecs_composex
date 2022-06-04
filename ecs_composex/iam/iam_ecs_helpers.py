#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template, AWSObject
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import Ref, Sub
from troposphere.iam import ManagedPolicy

from ecs_composex.common.cfn_conditions import define_stack_name


def add_ecs_execution_role_managed_policy(
    template: Template,
) -> ManagedPolicy | AWSObject:
    """
    Creates a blanket IAM Managed policy to use for the ECS Execution roles

    :param troposphere.Template template:
    :return: The managed policy
    :rtype: ManagedPolicy
    """
    policy_logical_id = "ECSExecutionRoleCommonRequirements"
    if policy_logical_id not in template.resources:
        managed_policy = template.add_resource(
            ManagedPolicy(
                policy_logical_id,
                Description=Sub(
                    r"Managed policy for ECS Execution role in ${STACK_NAME})",
                    STACK_NAME=define_stack_name(),
                ),
                Roles=[],
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AllowsForEcrPullFromEcsAgent",
                            "Effect": "Allow",
                            "Action": [
                                "ecr:GetAuthorizationToken",
                                "ecr:BatchCheckLayerAvailability",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:GetRepositoryPolicy",
                                "ecr:DescribeRepositories",
                                "ecr:ListImages",
                                "ecr:DescribeImages",
                                "ecr:BatchGetImage",
                            ],
                            "Resource": ["*"],
                        },
                        {
                            "Sid": "AllowEcsAgentOrientedTasks",
                            "Effect": "Allow",
                            "Action": [
                                "ecs:DiscoverPollEndpoint",
                                "ecs:Poll",
                                "ecs:Submit*",
                            ],
                            "Resource": ["*"],
                        },
                        {
                            "Sid": "AllowElbv2Actions",
                            "Effect": "Allow",
                            "Action": [
                                "elasticloadbalancing:DeregisterInstancesFromLoadBalancer",
                                "elasticloadbalancing:DeregisterTargets",
                                "elasticloadbalancing:Describe*",
                                "elasticloadbalancing:RegisterInstancesWithLoadBalancer",
                                "elasticloadbalancing:RegisterTargets",
                            ],
                            "Resource": ["*"],
                        },
                        {
                            "Sid": "AllowsEC2Actions",
                            "Effect": "Allow",
                            "Action": [
                                "ec2:AttachNetworkInterface",
                                "ec2:CreateNetworkInterface",
                                "ec2:CreateNetworkInterfacePermission",
                                "ec2:DeleteNetworkInterface",
                                "ec2:DeleteNetworkInterfacePermission",
                                "ec2:Describe*",
                                "ec2:DetachNetworkInterface",
                            ],
                            "Resource": ["*"],
                        },
                    ],
                },
            )
        )
        return managed_policy
    else:
        return template.resources[policy_logical_id]


def import_family_roles(
    settings: ComposeXSettings, exec_role_managed_policy: ManagedPolicy
) -> list:
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param troposphere.iam.ManagedPolicy exec_role_managed_policy:
    """
    roles = []
    for family in settings.families.values():
        roles.append(family.iam_manager.task_role)
        roles.append(family.iam_manager.exec_role)
        family.iam_manager.add_new_managed_policy(
            Ref(exec_role_managed_policy),
            role_name=family.iam_manager.exec_role._role_type,
        )
    return roles
