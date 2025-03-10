#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.compose.compose_services import ComposeService
    from troposphere.iam import Role

from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_PARTITION,
    AWS_REGION,
    MAX_PARAMETERS,
    FindInMap,
    GetAtt,
    NoValue,
    Ref,
    Sub,
)
from troposphere.ecs import Environment
from troposphere.iam import Policy, PolicyType

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters
from ecs_composex.ecs.ecs_params import EXEC_ROLE_T, TASK_ROLE_T


def handle_same_task_services_dependencies(services_config: list) -> None:
    """
    Function to define inter-tasks dependencies.
    It defines a priority value (service[0]) based on how many parents
    (i.e, they depend on the parents) they have. The lowest priority value
    are the first ones to have to start, the highest value is the last container
    to start.

    :param list[list[]] services_config:
    """
    for config in services_config:
        LOG.debug(config[1].depends_on)
        LOG.debug(
            any(k in [j[1].name for j in services_config] for k in config[1].depends_on)
        )
        if config[1].depends_on and any(
            k in [j[1].name for j in services_config] for k in config[1].depends_on
        ):
            parents = [
                s_service[1]
                for s_service in services_config
                if s_service[1].name in config[1].depends_on
            ]
            parents_dependency = [
                {
                    "ContainerName": p.name,
                    "Condition": p.container_start_condition,
                }
                for p in parents
            ]
            setattr(config[1].container_definition, "DependsOn", parents_dependency)
            for _ in parents:
                config[0] += 1


def ensure_essential_containers(family: ComposeFamily) -> None:
    """
    Iterates over the services of the family, and ensures that containers.Essential is set
    appropriately according to the service requirements

    :param family:
    """
    if len(family.ordered_services) == 1:
        LOG.debug("There is only one service, we need to ensure it is essential")
        family.ordered_services[0].is_essential = True


def assign_policy_to_role(role_secrets, role: Role) -> None:
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


def assign_secrets_to_roles(secrets, exec_role: Role, task_role: Role) -> None:
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


def set_ecs_cluster_logging_s3_access(
    settings: ComposeXSettings, policy, role_stack: ComposeXStack
):
    """
    Based on ECS Cluster settings / configurations, grant permissions to put logs to S3 Bucket for logs defined to log
    ECS Execute command feature

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param policy:
    :param ecs_composex.common.stacks.ComposeXStack role_stack:
    """
    if settings.ecs_cluster.log_bucket and settings.ecs_cluster.log_bucket != NoValue:
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


def set_ecs_cluster_logging_kms_access(
    settings: ComposeXSettings, policy, role_stack: ComposeXStack
):
    """
    Based on ECS Cluster settings / configurations, grant permissions to KMS key encrypting Log defined to log
    ECS Execute command feature

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param policy:
    :param ecs_composex.common.stacks.ComposeXStack role_stack:
    """
    if settings.ecs_cluster.log_key and settings.ecs_cluster.log_key != NoValue:
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


def set_ecs_cluster_logging_cw_access(
    settings: ComposeXSettings, policy, role_stack: ComposeXStack
) -> None:
    """
    Based on ECS Cluster settings / configurations, grant permissions to CW Log defined to log
    ECS Execute command feature

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param policy:
    :param ecs_composex.common.stacks.ComposeXStack role_stack:
    """
    if settings.ecs_cluster.log_group and settings.ecs_cluster.log_group != NoValue:
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


def set_ecs_cluster_logging_access(
    settings: ComposeXSettings, policy, role_stack: ComposeXStack
) -> None:
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


def set_service_dependency_on_all_iam_policies(family: ComposeFamily) -> None:
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


def update_env_var_to_parameter(
    family: ComposeFamily,
    service: ComposeService,
    env_var: Environment,
    set_as_params: Union[list, dict],
) -> None:
    """
    Function that will replace a user-defined environment variable with a Template Parameter
    If the SetAsParameter is a list, goes through them and generates the CFN Parameter properties
    If SetAsParameter is a dict, it will import the user-defined Parameter settings.
    """
    type_to_param_type: dict = {str: "String", int: "Number", float: "Number"}
    for var_name in set_as_params:
        if env_var.Name != var_name:
            continue
        if env_var.Name not in service.environment:
            continue
        parameter_title: str = NONALPHANUM.sub("", var_name)
        if type(service.environment[var_name]):
            LOG.warning(
                "{}.{} - Env var values have to be string. Value will be cast with Sub".format(
                    family.name, service.name
                )
            )
        if isinstance(set_as_params, list):
            env_var_param = Parameter(
                parameter_title,
                group_label="User Defined Service Variable",
                Type=type_to_param_type[type(service.environment[var_name])],
            )
        elif isinstance(set_as_params, dict):
            if (
                "Type" in set_as_params[var_name]
                and set_as_params[var_name]["Type"].find("List") >= 0
            ):
                raise ValueError(
                    "{}.{} - For environment variables, Parameter property Type cannot be a List. Got {}".format(
                        family.name, service.name, set_as_params[var_name]["Type"]
                    )
                )
            env_var_param = Parameter(
                parameter_title,
                group_label="User Defined Service Variable",
                **set_as_params[var_name],
            )
        else:
            raise TypeError(
                "services.{} - Value for x-environment.SetAsParameter must be either a list or mapping/dict. Got",
                type(set_as_params),
            )
        add_parameters(family.template, [env_var_param])
        family.stack.Parameters.update(
            {env_var_param.title: service.environment[var_name]}
        )
        setattr(env_var, "Value", Sub(f"${{{env_var_param.title}}}"))


def swap_environment_value_with_parameter(
    family: ComposeFamily, service: ComposeService
) -> None:
    set_as_params = service.x_environment["SetAsParameter"]
    for env_var in service.cfn_environment:
        if len(family.stack.Parameters) > MAX_PARAMETERS:
            LOG.warning(
                "{}.{} - Too many parameters already set for this stack".format(
                    family.name, service.name
                )
            )
            break
        if not isinstance(env_var, Environment):
            continue
        if not isinstance(env_var.Value, (str, int, float)):
            LOG.debug(
                "Env var {} is not str or int. Cannot convert. Got {}".format(
                    env_var.Name, type(env_var.Value)
                ),
            )
            continue
        update_env_var_to_parameter(family, service, env_var, set_as_params)
