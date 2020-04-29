# -*- coding: utf-8 -*-
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
from ecs_composex.iam import service_role_trust_policy


def add_service_roles(template):
    """
    Function to create the IAM roles for the ECS task

    :param template: service template to add the resources to
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
        PolicyName=Sub(f"EcsExecRole"),
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
                    "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": [
                        Sub(
                            "arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:"
                            f"${{{CLUSTER_NAME_T}}}:*"
                        )
                    ],
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
    Role(
        TASK_ROLE_T,
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
        Description=Sub(f"TaskRole - ${{{SERVICE_NAME_T}}} in ${{{CLUSTER_NAME_T}}}"),
        ManagedPolicyArns=[],
        Policies=[],
    )


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
