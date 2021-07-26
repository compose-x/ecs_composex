#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from troposphere import Sub
from troposphere.iam import Policy, Role

from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME_T,
    EXEC_ROLE_T,
    SERVICE_NAME_T,
    TASK_ROLE_T,
    TASK_T,
)
from ecs_composex.iam import service_role_trust_policy


def add_service_roles(task_family):
    """
    Function to create the IAM roles for the ECS task

    :param task_family: The task family to add the roles to
    :type task_family: ecs_composex.common.compose_services.ComposeFamily
    """
    task_family.exec_role = Role(
        EXEC_ROLE_T,
        AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
        Description=Sub(
            f"Execution role for ${{{SERVICE_NAME_T}}} in ${{{CLUSTER_NAME_T}}}"
        ),
        ManagedPolicyArns=[],
        Policies=[
            Policy(
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
                            "Action": [
                                "ecs:DiscoverPollEndpoint",
                                "ecs:Poll",
                                "ecs:Submit*",
                            ],
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
            )
        ],
    )
    task_family.task_role = Role(
        TASK_ROLE_T,
        AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
        Description=Sub(f"TaskRole - ${{{SERVICE_NAME_T}}} in ${{{CLUSTER_NAME_T}}}"),
        ManagedPolicyArns=[],
        Policies=[],
    )
    if TASK_ROLE_T not in task_family.template.resources:
        task_family.template.add_resource(task_family.task_role)
    if EXEC_ROLE_T not in task_family.template.resources:
        task_family.template.add_resource(task_family.exec_role)


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
