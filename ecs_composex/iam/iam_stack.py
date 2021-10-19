#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Output, Ref, Sub
from troposphere.iam import Policy
from troposphere.iam import Role as IamRole

from ecs_composex.common import add_outputs, add_parameters, build_template
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.iam.iam_params import (
    IAM_ROLE,
    IAM_ROLE_ARN,
    IAM_ROLE_ID,
    MAPPINGS_KEY,
)


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
        self.stack = None
        self.logical_name = f"{self.family.logical_name}{role_type}"
        self.cfn_resource = None
        self.init_role(role_type)
        self.mapping_key = MAPPINGS_KEY

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
        self.outputs = []
        self.lookup = {}

    def init_role(self, role_type):
        if role_type == "ExecRole":
            self.cfn_resource = IamRole(
                self.logical_name,
                AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
                Description=Sub(
                    f"Execution role for {self.family.logical_name} in ${{{CLUSTER_NAME.title}}}"
                ),
                ManagedPolicyArns=[],
                Policies=[
                    Policy(
                        PolicyName="EcsExecRole",
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
                    f"TaskRole - {self.family.logical_name} in ${{{CLUSTER_NAME.title}}}"
                ),
                ManagedPolicyArns=[],
                Policies=[],
            )

    def set_new_resource_outputs(self, output_definition):
        """
        Method to define the outputs for the resource when new
        """
        if output_definition[2] is Ref:
            value = Ref(output_definition[1])
        elif output_definition[2] is GetAtt:
            value = GetAtt(output_definition[1], output_definition[3])
        elif output_definition[2] is Sub:
            value = Sub(output_definition[3])
        else:
            raise TypeError(
                f"3rd argument for {output_definition[0]} must be one of",
                (Ref, GetAtt, Sub),
                "Got",
                output_definition[2],
            )
        return value

    def generate_outputs(self):
        """
        Method to create the outputs for XResources
        """
        if self.stack and not self.stack.is_void:
            root_stack = self.stack.title
        else:
            root_stack = self.mapping_key
        for (
            attribute_parameter,
            output_definition,
        ) in self.output_properties.items():
            output_name = f"{self.logical_name}{attribute_parameter.title}"
            if self.lookup:
                self.attributes_outputs[attribute_parameter] = {
                    "Name": output_name,
                    "ImportValue": self.set_attributes_from_mapping(
                        attribute_parameter
                    ),
                    "ImportParameter": None,
                }
            else:
                value = self.set_new_resource_outputs(output_definition)
                self.attributes_outputs[attribute_parameter] = {
                    "Name": output_name,
                    "Output": Output(output_name, Value=value),
                    "ImportParameter": Parameter(
                        output_name,
                        return_value=attribute_parameter.return_value,
                        Type=attribute_parameter.Type,
                    ),
                    "ImportValue": GetAtt(
                        root_stack,
                        f"Outputs.{output_name}",
                    ),
                    "Original": attribute_parameter,
                }
        for attr in self.attributes_outputs.values():
            if keyisset("Output", attr):
                self.outputs.append(attr["Output"])


def create_new_roles(settings):
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    roles = []
    for family in settings.families.values():
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
        add_parameters(stack_template, [CLUSTER_NAME])
        super().__init__(name, stack_template, **kwargs)
        self.Parameters.update(
            {CLUSTER_NAME.title: settings.ecs_cluster.cluster_identifier}
        )
        new_roles = create_new_roles(settings)
        for role in new_roles:
            self.stack_template.add_resource(role.cfn_resource)
            role.stack = self
            role.generate_outputs()
            add_outputs(stack_template, role.outputs)
            role.arn = role.attributes_outputs[IAM_ROLE_ARN]
            role.name = role.attributes_outputs[IAM_ROLE]
