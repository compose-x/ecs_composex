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
Represent a service from the docker-compose services
"""

from troposphere import Sub, AWS_PARTITION, AWS_REGION, AWS_ACCOUNT_ID
from troposphere.ecs import Secret as EcsSecret

from ecs_composex.common import LOG, keyisset
from ecs_composex.ecs.ecs_params import TASK_ROLE_T, EXEC_ROLE_T

RES_KEY = "secrets"
XRES_KEY = "x-secrets"


def match_secrets_services_config(service, s_secret, secrets):
    """
    Function to match the services and secrets
    :param service:
    :param s_secret:
    :param secrets:
    :return:
    """
    if isinstance(s_secret, str):
        secret_name = s_secret
    elif isinstance(s_secret, dict) and keyisset("source", s_secret):
        secret_name = s_secret["source"]
    else:
        raise LookupError("Could not identify the secret source", s_secret)
    for gl_secret in secrets:
        if gl_secret.name == secret_name:
            LOG.info(f"Matched secret {gl_secret.name} with {service.name}")
            service.secrets.append(gl_secret)
            gl_secret.services.append(service)


class ComposeSecret(object):
    """
    Class to represent a Compose secret.
    """

    main_key = "secrets"

    def __init__(self, name, definition):
        self.services = []
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
        if not isinstance(self.links, list):
            raise TypeError("LinksTo must be of type", list, "Got", type(self.links))
        for link in self.links:
            if link not in [EXEC_ROLE_T, TASK_ROLE_T]:
                raise ValueError(
                    "Links in LinksTo can only be one of",
                    EXEC_ROLE_T,
                    TASK_ROLE_T,
                    "Got",
                    link,
                )
