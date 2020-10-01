# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" IAM Building block for ECS """

from troposphere import Sub, Ref
from troposphere.iam import Role, PolicyType

from ecs_composex.ecs.ecs_params import (
    SERVICE_NAME_T,
    CLUSTER_NAME_T,
    EXEC_ROLE_T,
    TASK_ROLE_T,
    TASK_T,
)
from ecs_composex.iam import service_role_trust_policy, add_role_boundaries


def add_service_roles(template):
    """
    Function to create the IAM roles for the ECS task

    :param config: ecs_service configuration
    :type config: ecs_composex.ecs.ServiceConfig
    :param template: ecs_service template to add the resources to
    :type template: troposphere.Template
    """
    execution_role = Role(
        EXEC_ROLE_T,
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
        Description=Sub(
            f"Execution role for ${{{SERVICE_NAME_T}}} in ${{{CLUSTER_NAME_T}}}"
        ),
    )
    PolicyType(
        f"{EXEC_ROLE_T}Policy",
        template=template,
        PolicyName=Sub("EcsExecRole"),
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
                    "Action": ["ecs:DiscoverPollEndpoint", "ecs:Poll", "ecs:Submit*"],
                    "Resource": ["*"],
                },
                {
                    "Sid": "AllowsEcsAgentToPerformActionsForMicroservice",
                    "Effect": "Allow",
                    "Action": [
                        "ec2:AttachNetworkInterface",
                        "ec2:CreateNetworkInterface",
                        "ec2:CreateNetworkInterfacePermission",
                        "ec2:DeleteNetworkInterface",
                        "ec2:DeleteNetworkInterfacePermission",
                        "ec2:Describe*",
                        "ec2:DetachNetworkInterface",
                        "elasticloadbalancing:DeregisterInstancesFromLoadBalancer",
                        "elasticloadbalancing:DeregisterTargets",
                        "elasticloadbalancing:Describe*",
                        "elasticloadbalancing:RegisterInstancesWithLoadBalancer",
                        "elasticloadbalancing:RegisterTargets",
                    ],
                    "Resource": ["*"],
                },
            ],
        },
        Roles=[Ref(execution_role)],
    )
    policies = []
    managed_policies = []
    Role(
        TASK_ROLE_T,
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
        Description=Sub(f"TaskRole - ${{{SERVICE_NAME_T}}} in ${{{CLUSTER_NAME_T}}}"),
        ManagedPolicyArns=managed_policies,
        Policies=policies,
    )


def expand_role_polices(template, config):
    """
    Function to expand the role policies

    :param config:
    :param troposphere.Template template:
    :return:
    """
    exec_role = template.resources[EXEC_ROLE_T]
    task_role = template.resources[TASK_ROLE_T]
    if config and config.use_xray:
        if hasattr(task_role, "ManagedPolicyArns"):
            task_role.ManagedPolicyArns.append(
                "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
            )
        else:
            setattr(
                task_role,
                "ManagedPolicyArns",
                ["arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"],
            )
    if config and config.boundary:
        add_role_boundaries(task_role, config.boundary)
        add_role_boundaries(exec_role, config.boundary)
    if config and config.policies:
        task_role.Policies += config.policies
    if config and config.managed_policies:
        task_role.ManagedPolicyArns += config.managed_policies


def define_service_containers(service_template):
    """Function to set the containers list from the service_task definition object

    :param service_template: the task definition
    :type service_template: troposphere.Template

    :return: list of containers
    :rtype: list
    """
    service_task = None
    if TASK_T in service_template.resources:
        service_task = service_template.resources[TASK_T]
    try:
        if service_task:
            containers = getattr(service_task, "ContainerDefinitions")
        else:
            containers = []
    except AttributeError:
        raise ValueError(
            "Service Task definition defined but no ContainerDefinitions found"
        )
    return containers
