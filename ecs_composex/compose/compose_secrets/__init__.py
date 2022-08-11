#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x

"""
Package to manage docker-compose secrets
"""

import re
from copy import deepcopy

from compose_x_common.aws.kms import KMS_KEY_ARN_RE
from compose_x_common.aws.secrets_manager import get_secret_name_from_arn
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, FindInMap, Sub
from troposphere.ecs import Environment as EcsEnvVar
from troposphere.ecs import Secret as EcsSecret

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.ecs.ecs_params import EXEC_ROLE_T, TASK_ROLE_T
from ecs_composex.secrets.secrets_aws import lookup_secret_config
from ecs_composex.secrets.secrets_params import RES_KEY, XRES_KEY

from .helpers import define_env_var_name


class ComposeSecret:
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

    def __init__(self, name, definition, settings):
        """
        Method to init Secret for ECS ComposeX

        :param str name:
        :param dict definition:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.services = []
        self.name = name
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.definition = deepcopy(definition)
        self.links = [EXEC_ROLE_T, TASK_ROLE_T]
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
        if self.mapping:
            settings.secrets_mappings.update({self.logical_name: self.mapping})
            self.add_json_keys()

    @property
    def env_var(self) -> EcsEnvVar:
        env_var_name = set_else_none(
            "VarName",
            set_else_none("x-secrets", self.definition, alt_value={}),
            alt_value=re.sub(r"\W+", "", self.name.replace("-", "_").upper()),
        )
        return EcsEnvVar(Name=env_var_name, Value=self.arn)

    def define_secret(self, secret_name, json_key) -> EcsSecret:
        if isinstance(self.arn, str):
            secret = EcsSecret(Name=secret_name, ValueFrom=f"{self.arn}:{json_key}::")
        elif isinstance(self.arn, Sub):
            secret = EcsSecret(
                Name=secret_name,
                ValueFrom=Sub(
                    f"arn:${{{AWS_PARTITION}}}:secretsmanager:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                    f"secret:${{SecretName}}:{json_key}::",
                    SecretName=FindInMap(
                        self.map_name,
                        self.logical_name,
                        self.map_name_name,
                    ),
                ),
            )
        elif isinstance(self.arn, FindInMap):
            secret = EcsSecret(
                Name=secret_name,
                ValueFrom=Sub(
                    f"${{SecretArn}}:{json_key}::",
                    SecretArn=FindInMap(
                        self.map_name,
                        self.logical_name,
                        self.map_arn_name,
                    ),
                ),
            )
        else:
            raise TypeError(
                f"secrets.{self.name} - ARN is",
                type(self.arn),
                "must be one of",
                str,
                Sub,
                FindInMap,
            )
        return secret

    def add_json_keys(self):
        """
        Add secrets definitions based on JSON secret keys
        """
        if not keyisset(self.json_keys_key, self.definition[self.x_key]):
            return
        unfiltered_secrets = self.definition[self.x_key][self.json_keys_key]
        filtered_secrets = [
            dict(y) for y in {tuple(x.items()) for x in unfiltered_secrets}
        ]
        old_secrets = deepcopy(self.ecs_secret)
        secrets_to_map = {}
        self.ecs_secret = []
        for secret_json_key in filtered_secrets:
            secret_key = secret_json_key["SecretKey"]
            secret_name = define_env_var_name(secret_json_key)
            if secret_name not in secrets_to_map:
                secrets_to_map[secret_name] = self.define_secret(
                    secret_name, secret_key
                )
            else:
                LOG.warning(
                    f"secrets.{self.name} - Secret VarName {secret_name} already defined. Overriding value"
                )
                secrets_to_map[secret_name] = self.define_secret(
                    secret_name, secret_key
                )
        self.ecs_secret = [
            _defined_secret for _defined_secret in secrets_to_map.values()
        ]
        if not self.ecs_secret:
            self.ecs_secret = old_secrets

    def define_names_from_import(self):
        """
        Define the names from docker-compose file content
        """
        if not keyisset(self.map_name_name, self.definition[self.x_key]):
            raise KeyError(
                f"Missing {self.map_name_name} when doing non-lookup import for {self.name}"
            )
        name_input = self.definition[self.x_key][self.map_name_name]
        if name_input.startswith("arn:"):
            self.aws_name = get_secret_name_from_arn(
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
                    f"secrets.{self.name} - When specifying {self.map_kms_name} you must specify the full ARN"
                )
            else:
                self.mapping[self.map_kms_name] = self.definition[self.map_kms_name]
                self.kms_key_arn = FindInMap(
                    self.map_name, self.logical_name, self.map_kms_name
                )

    def define_names_from_lookup(self, session):
        """
        Method to Lookup the secret based on its tags.
        """
        lookup_info = self.definition[self.x_key]["Lookup"]
        if keyisset("Name", self.definition[self.x_key]):
            lookup_info["Name"] = self.definition[self.x_key]["Name"]
        secret_config = lookup_secret_config(self.logical_name, lookup_info, session)
        self.aws_name = get_secret_name_from_arn(secret_config[self.logical_name])
        self.arn = secret_config[self.logical_name]
        self.iam_arn = secret_config[self.logical_name]
        if keyisset("KmsKeyId", secret_config) and not secret_config[
            "KmsKeyId"
        ].startswith("alias"):
            self.kms_key = secret_config["KmsKeyId"]
        elif keyisset("KmsKeyId", secret_config) and secret_config[
            "KmsKeyId"
        ].startswith("alias"):
            LOG.warning(
                f"secrets.{self.name} - The KMS Key retrieved is a KMS Key Alias, not importing."
            )

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
        """
        Defines which IAM role to assign the secrets access policy to. Defaults to exec role
        """
        if keyisset(self.links_key, self.definition[self.x_key]):
            self.links = self.definition[self.x_key][self.links_key]
