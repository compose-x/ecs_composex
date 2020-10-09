#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to parse secrets from the compose content file.
"""

from troposphere import Sub, AWS_PARTITION, AWS_REGION, AWS_ACCOUNT_ID
from troposphere.ecs import Secret as EcsSecret
from troposphere.iam import Policy

from ecs_composex.common import LOG, keyisset, NONALPHANUM
from ecs_composex.ecs.ecs_container_config import extend_container_secrets
from ecs_composex.ecs.ecs_params import TASK_ROLE_T, EXEC_ROLE_T

RES_KEY = "secrets"
XRES_KEY = "x-secrets"


class ComposeSecret(object):
    """
    Class to represent a Compose secret.
    """

    def __init__(self, name, definition):
        if not keyisset("Name", definition[XRES_KEY]):
            raise KeyError(f"Missing Name in the {XRES_KEY} defintion")
        self.name = name
        aws_name = definition[XRES_KEY]["Name"]
        if aws_name.startswith("arn:"):
            self.aws_name = definition[XRES_KEY]["Name"]
            self.aws_iam_name = definition[XRES_KEY]["Name"]
        else:
            self.aws_name = Sub(
                f"arn:${{{AWS_PARTITION}}}:secretsmanager:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:secret:{aws_name}"
            )
            self.aws_iam_name = Sub(
                f"arn:${{{AWS_PARTITION}}}:secretsmanager:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:secret:{aws_name}*"
            )
        self.links = (
            definition[XRES_KEY]["LinksTo"]
            if keyisset("LinksTo", definition[XRES_KEY])
            else [EXEC_ROLE_T]
        )
        self.ecs_secret = EcsSecret(Name=self.name, ValueFrom=self.aws_name)

        self.validate_links()

    def validate_links(self):
        for link in self.links:
            if link not in [EXEC_ROLE_T, TASK_ROLE_T]:
                raise ValueError(
                    "Links in LinksTo can only be one of",
                    EXEC_ROLE_T,
                    TASK_ROLE_T,
                    "Got",
                    link,
                )

    def assign_to_task_definition(self, template, container):
        """
        Method to add the secret to the given task definition

        :param troposphere.Template template:
        :param troposphere.ecs.ContainerDefinition container:
        :return:
        """
        task_role = template.resources[TASK_ROLE_T]
        exec_role = template.resources[EXEC_ROLE_T]
        policy = Policy(
            PolicyName=f"AccessSecret{NONALPHANUM.sub('', self.name)}",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": ["secretsmanager:GetSecretValue"],
                        "Effect": "Allow",
                        "Resource": self.aws_iam_name,
                        "Sid": f"AccessToSecret{NONALPHANUM.sub('', self.name)}",
                    }
                ],
            },
        )
        if EXEC_ROLE_T in self.links:
            if hasattr(exec_role, "Policies"):
                exec_role.Policies.append(policy)
            elif not hasattr(exec_role, "Policies"):
                setattr(exec_role, "Policies", [policy])
            extend_container_secrets(container, self.ecs_secret)
        else:
            LOG.warn(
                f"You did not specify {EXEC_ROLE_T} in your LinksTo for this secret. You will not have ECS"
                "Expose the value of the secret to your container."
            )
        if TASK_ROLE_T in self.links and hasattr(task_role, "Policies"):
            task_role.Policies.append(policy)
        elif TASK_ROLE_T in self.links and not hasattr(task_role, "Policies"):
            setattr(task_role, "Policies", [policy])


def parse_secrets(settings):
    """
    Function to parse the settings compose content and define the secrets.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if not keyisset(RES_KEY, settings.compose_content):
        return
    secrets = settings.compose_content[RES_KEY]
    for secret_name in secrets:
        secret_def = secrets[secret_name]
        if keyisset("external", secret_def):
            LOG.info(f"Adding secret {secret_name} to settings")
            secret_def["ComposeSecret"] = ComposeSecret(secret_name, secret_def)
