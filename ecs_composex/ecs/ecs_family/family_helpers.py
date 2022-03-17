#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_PARTITION,
    AWS_REGION,
    FindInMap,
    GetAtt,
    Ref,
    Sub,
)
from troposphere.iam import Policy, PolicyType

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.ecs_params import EXEC_ROLE_T, TASK_ROLE_T


def handle_same_task_services_dependencies(services_config):
    """
    Function to define inter-tasks dependencies.
    It defines a priority value (service[0]) based on how many parents
    (i.e, they depend on the parents) they have. The lowest priority value
    are the first ones to have to start, the highest value is the last container
    to start.

    :param list[list[]] services_config:
    """
    for service in services_config:
        LOG.debug(service[1].depends_on)
        LOG.debug(
            any(
                k in [j[1].name for j in services_config] for k in service[1].depends_on
            )
        )
        if service[1].depends_on and any(
            k in [j[1].name for j in services_config] for k in service[1].depends_on
        ):
            service[1].container_definition.Essential = False
            parents = [
                s_service[1]
                for s_service in services_config
                if s_service[1].name in service[1].depends_on
            ]
            parents_dependency = [
                {
                    "ContainerName": p.name,
                    "Condition": p.container_start_condition,
                }
                for p in parents
            ]
            setattr(service[1].container_definition, "DependsOn", parents_dependency)
            for _ in parents:
                service[0] += 1


def define_essential_containers(family, ordered_containers_config):
    for service in family.ordered_services:
        if (
            service.container_start_condition == "SUCCESS"
            or service.container_start_condition == "COMPLETE"
            or service.is_aws_sidecar
            or not service.is_essential
        ):
            setattr(service.container_definition, "Essential", False)
        else:
            setattr(service.container_definition, "Essential", True)

    if len(ordered_containers_config) == 1:
        LOG.debug("There is only one service, we need to ensure it is essential")
        setattr(ordered_containers_config[0][1].container_definition, "Essential", True)


def assign_policy_to_role(role_secrets, role):
    """
    Function to assign the policy to role Policies
    :param list role_secrets:
    :param troposphere.iam.Role role:
    :return:
    """

    secrets_list = [secret.iam_arn for secret in role_secrets]
    secrets_kms_keys = [secret.kms_key_arn for secret in role_secrets if secret.kms_key]
    secrets_statement = {
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue"],
        "Sid": "AllowSecretsAccess",
        "Resource": [secret for secret in secrets_list],
    }
    secrets_keys_statement = {}
    if secrets_kms_keys:
        secrets_keys_statement = {
            "Effect": "Allow",
            "Action": ["kms:Decrypt"],
            "Sid": "AllowSecretsKmsKeyDecrypt",
            "Resource": [kms_key for kms_key in secrets_kms_keys],
        }
    role_policy = Policy(
        PolicyName="AccessToPreDefinedSecrets",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [secrets_statement],
        },
    )
    if secrets_keys_statement:
        role_policy.PolicyDocument["Statement"].append(secrets_keys_statement)

    if hasattr(role, "Policies") and isinstance(role.Policies, list):
        existing_policy_names = [
            policy.PolicyName for policy in getattr(role, "Policies")
        ]
        if role_policy.PolicyName not in existing_policy_names:
            role.Policies.append(role_policy)
    else:
        setattr(role, "Policies", [role_policy])


def assign_secrets_to_roles(secrets, exec_role, task_role):
    """
    Function to assign secrets access policies to exec_role and/or task_role

    :param secrets:
    :param exec_role:
    :param task_role:
    :return:
    """
    exec_role_secrets = [secret for secret in secrets if EXEC_ROLE_T in secret.links]
    task_role_secrets = [secret for secret in secrets if TASK_ROLE_T in secret.links]
    LOG.debug(exec_role_secrets)
    LOG.debug(task_role_secrets)
    for secret in secrets:
        if EXEC_ROLE_T not in secret.links:
            LOG.warning(
                f"You did not specify {EXEC_ROLE_T} in your LinksTo for this secret. You will not have ECS"
                "Expose the value of the secret to your container."
            )
    if exec_role_secrets:
        assign_policy_to_role(exec_role_secrets, exec_role)
    if task_role_secrets:
        assign_policy_to_role(task_role_secrets, task_role)


def set_ecs_cluster_logging_s3_access(settings, policy, role_stack):
    """
    Based on ECS Cluster settings / configurations, grant permissions to put logs to S3 Bucket for logs defined to log
    ECS Execute command feature

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param policy:
    :param ecs_composex.common.stacks.ComposeXStack role_stack:
    """
    if settings.ecs_cluster.log_bucket:
        parameter = Parameter("EcsExecuteLoggingBucket", Type="String")
        add_parameters(role_stack.stack_template, [parameter])
        if isinstance(settings.ecs_cluster.log_bucket, FindInMap):
            role_stack.Parameters.update(
                {parameter.title: settings.ecs_cluster.log_bucket}
            )
        else:
            role_stack.Parameters.update(
                {parameter.title: Ref(settings.ecs_cluster.log_bucket.cfn_resource)}
            )
        policy.PolicyDocument["Statement"].append(
            {
                "Sid": "AllowDescribeS3Bucket",
                "Action": ["s3:GetEncryptionConfiguration"],
                "Resource": [
                    Sub(f"arn:${{{AWS_PARTITION}}}:s3:::${{{parameter.title}}}")
                ],
                "Effect": "Allow",
            }
        )
        policy.PolicyDocument["Statement"].append(
            {
                "Sid": "AllowS3BucketObjectWrite",
                "Action": ["s3:PutObject"],
                "Resource": [
                    Sub(f"arn:${{{AWS_PARTITION}}}:s3:::${{{parameter.title}}}/*")
                ],
                "Effect": "Allow",
            }
        )


def set_ecs_cluster_logging_kms_access(settings, policy, role_stack):
    """
    Based on ECS Cluster settings / configurations, grant permissions to KMS key encrypting Log defined to log
    ECS Execute command feature

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param policy:
    :param ecs_composex.common.stacks.ComposeXStack role_stack:
    """
    if settings.ecs_cluster.log_key:
        parameter = Parameter("EcsExecuteLoggingEncryptionKey", Type="String")
        add_parameters(role_stack.stack_template, [parameter])
        if isinstance(settings.ecs_cluster.log_key, FindInMap):
            role_stack.Parameters.update(
                {parameter.title: settings.ecs_cluster.log_key}
            )
        else:
            role_stack.Parameters.update(
                {
                    parameter.title: GetAtt(
                        settings.ecs_cluster.log_key.cfn_resource, "Arn"
                    )
                }
            )
        policy.PolicyDocument["Statement"].append(
            {
                "Action": [
                    "kms:Encrypt*",
                    "kms:Decrypt*",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:Describe*",
                ],
                "Resource": [Ref(parameter)],
                "Effect": "Allow",
            }
        )


def set_ecs_cluster_logging_cw_access(settings, policy, role_stack):
    """
    Based on ECS Cluster settings / configurations, grant permissions to CW Log defined to log
    ECS Execute command feature

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param policy:
    :param ecs_composex.common.stacks.ComposeXStack role_stack:
    """
    if settings.ecs_cluster.log_group:
        parameter = Parameter("EcsExecuteLoggingGroup", Type="String")
        add_parameters(role_stack.stack_template, [parameter])
        if isinstance(settings.ecs_cluster.log_group, FindInMap):
            role_stack.Parameters.update(
                {parameter.title: settings.ecs_cluster.log_group}
            )
            arn_value = Sub(
                f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:"
                f"${{{AWS_ACCOUNT_ID}}}:${{{parameter.title}}}:*"
            )
        else:
            role_stack.Parameters.update(
                {parameter.title: GetAtt(settings.ecs_cluster.log_group, "Arn")}
            )
            arn_value = Ref(parameter)
        policy.PolicyDocument["Statement"].append(
            {
                "Sid": "AllowDescribingAllCWLogGroupsForSSMClient",
                "Action": ["logs:DescribeLogGroups"],
                "Resource": ["*"],
                "Effect": "Allow",
            }
        )
        policy.PolicyDocument["Statement"].append(
            {
                "Action": [
                    "logs:CreateLogStream",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                ],
                "Resource": [arn_value],
                "Effect": "Allow",
            }
        )


def set_ecs_cluster_logging_access(settings, policy, role_stack):
    """
    Based on ECS Cluster settings / configurations, grant permissions to specific resources
    for all functionalities to work.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param policy:
    :param ecs_composex.common.stacks.ComposeXStack role_stack:
    """
    set_ecs_cluster_logging_kms_access(settings, policy, role_stack)
    set_ecs_cluster_logging_cw_access(settings, policy, role_stack)
    set_ecs_cluster_logging_s3_access(settings, policy, role_stack)


def set_service_dependency_on_all_iam_policies(family):
    """
    Function to ensure the Service does not get created/updated before all IAM policies were set completely
    """
    if not family.ecs_service.ecs_service:
        return
    policies = [
        p.title for p in family.template.resources.values() if isinstance(p, PolicyType)
    ]
    if hasattr(family.ecs_service.ecs_service, "DependsOn"):
        depends_on = getattr(family.ecs_service.ecs_service, "DependsOn")
        for policy in policies:
            if policy not in depends_on:
                depends_on.append(policy)
    else:
        setattr(family.ecs_service.ecs_service, "DependsOn", policies)
    LOG.debug(family.ecs_service.ecs_service.DependsOn)
