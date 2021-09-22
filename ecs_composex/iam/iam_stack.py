#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub
from troposphere.iam import Policy, PolicyType
from troposphere.iam import Role as IamRole

from ecs_composex.common import build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.iam.iam_params import IAM_ROLE, IAM_ROLE_ARN, IAM_ROLE_ID


class EcsRole(object):
    """
    Class to wrap around the AWS IAM Role
    """

    def __init__(self, family, role_type):
        """
        :param family: The family the role will belong to
        """
        if role_type not in ["TaskRole", "ExecRole"]:
            raise ValueError(
                "role_type is", role_type, "expected one of", ["TaskRole", "ExecRole"]
            )
        self.family = family
        self.logical_name = f"{self.family.logical_name}{role_type}"
        self.cfn_resource = None
        self.init_role(role_type)

        self.output_properties = {
            IAM_ROLE: (self.logical_name, self.cfn_resource, Ref, None),
            IAM_ROLE_ID: (
                f"{self.logical_name}{IAM_ROLE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                IAM_ROLE_ID.return_value,
            ),
            IAM_ROLE_ARN: (
                f"{self.logical_name}{IAM_ROLE_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                IAM_ROLE_ARN.return_value,
            ),
        }
        self.attributes_outputs = {}

    def init_role(self, role_type):
        if role_type == "ExecRole":
            self.cfn_resource = IamRole(
                self.logical_name,
                AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
                Description=Sub(
                    f"Execution role for {self.family.logical_name} in ${{{CLUSTER_NAME_T}}}"
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
        elif role_type == "TaskRole":
            self.cfn_resource = IamRole(
                self.logical_name,
                AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
                Description=Sub(
                    f"TaskRole - {self.family.logical_name} in ${{{CLUSTER_NAME_T}}}"
                ),
                ManagedPolicyArns=[],
                Policies=[],
            )

    def set_role_parameters(self, role_stack):
        pass


def create_new_roles(settings):
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    roles = []
    for family in settings.families:
        family.task_role = EcsRole(family, "TaskRole")
        family.exec_role = EcsRole(family, "ExecRole")
        roles.append(family.task_role)
        roles.append(family.exec_role)
    return roles


class XStack(ComposeXStack):
    """
    Class to represent the IAM top stack
    """

    def __init__(self, name, settings, **kwargs):
        stack_template = build_template("Root stack for IAM Roles")
        super().__init__(name, stack_template, **kwargs)
        new_roles = create_new_roles(settings)
        for role in new_roles:
            self.stack_template.add_resource(role)
