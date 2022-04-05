#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to enable ECS Anywhere feature for a given ECS Family.
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import Ref
from troposphere.ecs import LinuxParameters
from troposphere.iam import PolicyType

from ecs_composex.ecs.ecs_family.family_helpers import set_ecs_cluster_logging_access


def set_enable_execute_command(family):
    """
    Sets necessary settings to enable ECS Execute Command
    ECS Anywhere support since 2022-01-24
    """
    for svc in family.services:
        if svc.is_aws_sidecar:
            continue
        if svc.x_ecs and keyisset("EnableExecuteCommand", svc.x_ecs):
            family.enable_execute_command = True
    if (
        family.enable_execute_command
        and family.task_definition
        and family.task_definition.ContainerDefinitions
    ):
        for container in family.task_definition.ContainerDefinitions:
            if hasattr(container, "LinuxParameters"):
                params = getattr(container, "LinuxParameters")
                setattr(params, "InitProcessEnabled", True)
            else:
                setattr(
                    container,
                    "LinuxParameters",
                    LinuxParameters(InitProcessEnabled=True),
                )


def expand_policy_roles(role_stack, policy_title, task_role) -> None:
    """
    Adds the task role to the policy when the policy already exists

    :param role_stack:
    :param str policy_title:
    :param task_role:
    """
    policy = role_stack.stack_template.resources[policy_title]
    if hasattr(policy, "Roles"):
        roles = getattr(policy, "Roles")
        if roles:
            for role in roles:
                if isinstance(role, Ref) and role.data["Ref"] != task_role.data["Ref"]:
                    roles.append(task_role)
    else:
        setattr(policy, "Roles", [task_role])


def apply_ecs_execute_command_permissions(family, settings):
    """
    Set the IAM Policies in place to allow ECS Execute SSM and Logging

    :param settings:
    :return:
    """
    policy_title = "EnableEcsExecuteCommand"
    role_stack = family.iam_manager.task_role.stack
    task_role = Ref(family.iam_manager.task_role.cfn_resource)
    if policy_title not in role_stack.stack_template.resources:
        policy = role_stack.stack_template.add_resource(
            PolicyType(
                policy_title,
                PolicyName="EnableExecuteCommand",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "ssmmessages:CreateControlChannel",
                                "ssmmessages:CreateDataChannel",
                                "ssmmessages:OpenControlChannel",
                                "ssmmessages:OpenDataChannel",
                            ],
                            "Resource": "*",
                        }
                    ],
                },
                Roles=[task_role],
            )
        )
        set_ecs_cluster_logging_access(settings, policy, role_stack)
    else:
        expand_policy_roles(role_stack, policy_title, task_role)
    setattr(
        family.ecs_service.ecs_service,
        "EnableExecuteCommand",
        family.enable_execute_command,
    )
