﻿#  -*- coding: utf-8 -*-
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

import re
from copy import deepcopy

from troposphere import Sub, FindInMap
from troposphere import AWS_PARTITION, AWS_REGION, AWS_ACCOUNT_ID
from troposphere.ecs import Secret as EcsSecret

from ecs_composex.common import LOG, keyisset, NONALPHANUM
from ecs_composex.ecs.ecs_params import TASK_ROLE_T, EXEC_ROLE_T
from ecs_composex.kms.kms_params import KMS_KEY_ARN_RE
from ecs_composex.secrets.secrets_aws import lookup_secret_config
from ecs_composex.secrets.secrets_params import XRES_KEY, RES_KEY


def get_name_from_arn(secret_arn):
    secret_re = re.compile(
        r"(?:^arn:aws(?:-[a-z]+)?:secretsmanager:[\w-]+:[0-9]{12}:secret:)([\S]+)(?:-[A-Za-z0-9]{1,6})$"
    )
    if not secret_re.match(secret_arn):
        raise ValueError(
            "The secret ARN is invalid",
            secret_arn,
            "No name cound be found from it via",
            r"(?:^arn:aws(?:-[a-z]+)?:secretsmanager:[\w-]+:[0-9]{12}:secret:)([\S]+)(?:-[A-Za-z0-9]{1,6})$",
        )
    return secret_re.match(secret_arn).groups()[0]


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

    x_key = XRES_KEY
    main_key = "secrets"
    map_kms_name = "KmsKeyId"
    map_arn_name = "Arn"
    map_name_name = "Name"
    json_keys_key = "JsonKeys"
    links_key = "LinksTo"
    map_name = RES_KEY
    allowed_keys = ["Name", "Lookup"]
    valid_keys = [json_keys_key, links_key] + allowed_keys

    def __init__(self, name, definition, settings):
        """
        Method to init Secret for ECS ComposeX

        :param str name:
        :param dict definition:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.services = []
        if not any(key in definition[self.x_key].keys() for key in self.allowed_keys):
            raise KeyError(
                f"You must define at least one of",
                self.allowed_keys,
                "Got",
                definition.keys(),
            )
        elif not all(key in self.valid_keys for key in definition[self.x_key].keys()):
            raise KeyError(
                "Only valid keys are",
                self.valid_keys,
                "Got",
                definition[self.x_key].keys(),
            )
        self.name = name
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.definition = deepcopy(definition)
        self.links = [EXEC_ROLE_T]
        self.arn = None
        self.iam_arn = None
        self.aws_name = None
        self.kms_key = None
        self.kms_key_arn = None
        self.ecs_secret = []
        self.mapping = {}
        if not keyisset("Lookup", self.definition[self.x_key]):
            self.define_names_from_import()
        else:
            self.define_names_from_lookup(settings.session)

        self.define_links()
        self.validate_links()
        if self.mapping:
            settings.secrets_mappings.update({self.logical_name: self.mapping})
            self.add_json_keys()

    def add_json_keys(self):
        """
        Method to add secrets definitions based on JSON secret keys
        """
        if not keyisset(self.json_keys_key, self.definition[self.x_key]):
            return
        required_keys = ["Name", "Key"]
        for secret_key in self.definition[self.x_key][self.json_keys_key]:
            if not all(key in required_keys for key in secret_key):
                raise KeyError(
                    "For Secrets JSON Key support, you must specify",
                    required_keys,
                    "Got",
                    secret_key.keys(),
                )
            json_key = secret_key["Key"]
            secret_name = secret_key["Name"]
            if isinstance(self.arn, str):
                self.ecs_secret.append(
                    EcsSecret(Name=secret_name, ValueFrom=f"{self.arn}:{json_key}::")
                )
            elif isinstance(self.arn, Sub):
                self.ecs_secret.append(
                    EcsSecret(
                        Name=secret_name,
                        ValueFrom=Sub(
                            f"arn:${{{AWS_PARTITION}}}:secretsmanager:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                            f"secret:${{SecretName}}:{json_key}::",
                            SecretName=FindInMap(
                                self.map_name, self.logical_name, self.map_name_name
                            ),
                        ),
                    )
                )
            elif isinstance(self.arn, FindInMap):
                self.ecs_secret.append(
                    EcsSecret(
                        Name=secret_name,
                        ValueFrom=Sub(
                            f"${{SecretArn}}:{json_key}::",
                            SecretArn=FindInMap(
                                self.map_name, self.logical_name, self.map_arn_name
                            ),
                        ),
                    )
                )

    def define_names_from_import(self):
        """
        Method to define the names from docker-compose file content
        """
        if not keyisset(self.map_name_name, self.definition[self.x_key]):
            raise KeyError(
                f"Missing {self.map_name_name} when doing non-lookup import for {self.name}"
            )
        name_input = self.definition[self.x_key][self.map_name_name]
        if name_input.startswith("arn:"):
            self.aws_name = get_name_from_arn(
                self.definition[self.x_key][self.map_name_name]
            )
            self.mapping = {
                self.map_arn_name: name_input,
                self.map_name_name: self.aws_name,
            }
        else:
            self.aws_name = name_input
            self.mapping = {self.map_name_name: self.aws_name}
            self.arn = Sub(
                f"arn:${{{AWS_PARTITION}}}:secretsmanager:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                "secret:${SecretName}",
                SecretName=FindInMap(
                    self.map_name, self.logical_name, self.map_name_name
                ),
            )
            self.iam_arn = Sub(
                f"arn:${{{AWS_PARTITION}}}:secretsmanager:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                "secret:${SecretName}*",
                SecretName=FindInMap(
                    self.map_name, self.logical_name, self.map_name_name
                ),
            )
            self.ecs_secret = [EcsSecret(Name=self.name, ValueFrom=self.arn)]
        if keyisset(self.map_kms_name, self.definition):
            if not self.definition[self.map_kms_name].startswith(
                "arn:"
            ) or not KMS_KEY_ARN_RE.match(self.definition[self.map_kms_name]):
                LOG.error(
                    f"When specifying {self.map_kms_name} you must specify the full VALID ARN"
                )
            else:
                self.mapping[self.map_kms_name] = self.definition[self.map_kms_name]
                self.kms_key_arn = FindInMap(
                    self.map_name, self.logical_name, self.map_kms_name
                )

    def define_names_from_lookup(self, session):
        """
        Method to Lookup the secret based on its tags.
        :return:
        """
        lookup_info = self.definition[self.x_key]["Lookup"]
        if keyisset("Name", self.definition[self.x_key]):
            lookup_info["Name"] = self.definition[self.x_key]["Name"]
        secret_config = lookup_secret_config(self.logical_name, lookup_info, session)
        self.aws_name = get_name_from_arn(secret_config[self.logical_name])
        self.arn = secret_config[self.logical_name]
        self.iam_arn = secret_config[self.logical_name]
        if keyisset("KmsKeyId", secret_config) and not secret_config[
            "KmsKeyId"
        ].startswith("alias"):
            self.kms_key = secret_config["KmsKeyId"]
        elif keyisset("KmsKeyId", secret_config) and secret_config[
            "KmsKeyId"
        ].startswith("alias"):
            LOG.warning("The KMS Key retrieved is a KMS Key Alias, not importing.")

        self.mapping = {
            self.map_arn_name: secret_config[self.logical_name],
            self.map_name_name: secret_config[self.map_name_name],
        }
        if self.kms_key:
            self.mapping[self.map_kms_name] = self.kms_key
            self.kms_key_arn = FindInMap(
                self.map_name, self.logical_name, self.map_kms_name
            )
        self.arn = FindInMap(self.map_name, self.logical_name, self.map_arn_name)
        self.ecs_secret = [EcsSecret(Name=self.name, ValueFrom=self.arn)]

    def define_links(self):
        if keyisset(self.links_key, self.definition[self.x_key]):
            self.links = self.definition[self.x_key][self.links_key]

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
