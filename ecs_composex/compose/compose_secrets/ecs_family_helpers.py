#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere.ecs import RepositoryCredentials
from troposphere.iam import PolicyType

import ecs_composex.common.troposphere_tools


def identify_repo_credentials_secret(settings, task, secret_name):
    """
    Function to identify the secret_arn

    :param settings:
    :param ComposeFamily task:
    :param secret_name:
    :return:
    """
    for secret in settings.secrets:
        if secret.name == secret_name:
            secret_arn = secret.arn
            if secret_name not in [s.name for s in settings.secrets]:
                raise KeyError(
                    f"secret {secret_name} was not found in the defined secrets",
                    [s.name for s in settings.secrets],
                )
            if (
                secret.kms_key_arn
                and task.template
                and "RepositoryCredsKmsKeyAccess" not in task.template.resources
            ):
                task.template.add_resource(
                    PolicyType(
                        "RepositoryCredsKmsKeyAccess",
                        PolicyName="RepositoryCredsKmsKeyAccess",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["kms:Decrypt"],
                                    "Resource": [secret.kms_key_arn],
                                }
                            ],
                        },
                        Roles=[task.exec_role.name],
                    )
                )
            return secret_arn
    return None


def set_repository_credentials(family, settings):
    """
    Method to go over each service and identify which ones have credentials to pull the Docker image from a private
    repository

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for service in family.services:
        if not service.x_repo_credentials:
            continue
        if service.x_repo_credentials.startswith("arn:aws"):
            secret_arn = service.x_repo_credentials
        elif service.x_repo_credentials.startswith("secrets::"):
            secret_name = service.x_repo_credentials.split("::")[-1]
            secret_arn = identify_repo_credentials_secret(settings, family, secret_name)
        else:
            raise ValueError(
                "The secret for private repository must be either an ARN or the name of a secret defined in secrets"
            )
        setattr(
            service.container_definition,
            "RepositoryCredentials",
            RepositoryCredentials(CredentialsParameter=secret_arn),
        )
        policy = PolicyType(
            "AccessToRepoCredentialsSecret",
            PolicyName="AccessToRepoCredentialsSecret",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["secretsmanager:GetSecretValue"],
                        "Sid": "AccessToRepoCredentialsSecret",
                        "Resource": [secret_arn],
                    }
                ],
            },
            Roles=[family.iam_manager.exec_role.name],
        )
        if family.template and policy.title not in family.template.resources:
            family.template.add_resource(policy)
