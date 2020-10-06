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

from troposphere import Ref, Sub, If, AWS_PARTITION, AWS_ACCOUNT_ID
from troposphere.kms import Key, Alias
from ecs_composex.common import keyisset, LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import set_resources, XResource
from ecs_composex.kms import metadata
from ecs_composex.kms.kms_template import create_kms_template
from ecs_composex.kms.kms_params import RES_KEY


def define_default_key_policy():
    """
    Function to return the default KMS management policy allowing root account access.
    :return: policy
    :rtype: dict
    """
    policy = {
        "Version": "2012-10-17",
        "Id": "auto-secretsmanager-1",
        "Statement": [
            {
                "Sid": "Allow direct access to key metadata to the account",
                "Effect": "Allow",
                "Principal": {
                    "AWS": Sub(
                        f"arn:${{{AWS_PARTITION}}}:iam::${{{AWS_ACCOUNT_ID}}}:root"
                    )
                },
                "Action": ["kms:*"],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {"kms:CallerAccount": Ref(AWS_ACCOUNT_ID)}
                },
            }
        ],
    }
    return policy


class KmsKey(XResource):
    """
    Class to represent a KMS Key
    """

    def __init__(self, name, definition):
        super().__init__(name, definition)

    def define_kms_key(self):
        """
        Method to set the KMS Key
        """
        if not self.properties:
            self.properties = {
                "Description": Sub(
                    f"{self.name} created in ${{{ROOT_STACK_NAME.title}}}"
                ),
                "Enabled": True,
                "EnableKeyRotation": True,
                "KeyUsage": "ENCRYPT_DECRYPT",
                "PendingWindowInDays": 7,
            }
        if not keyisset("KeyPolicy", self.properties):
            self.properties.update({"KeyPolicy": define_default_key_policy()})
        self.properties.update({"Metadata": metadata})
        LOG.debug(self.properties)
        self.cfn_resource = Key(self.logical_name, **self.properties)

    def handle_key_settings(self, template):
        """
        Method to add to the template for additional KMS key related resources.

        :param troposphere.Template template:
        """
        if self.settings and keyisset("Alias", self.settings):
            alias_name = self.settings["Alias"]
            if not (alias_name.startswith("alias/") or alias_name.startswith("aws")):
                alias_name = If(
                    USE_STACK_NAME_CON_T,
                    Sub(f"alias/${{AWS::StackName}}/{alias_name}"),
                    Sub(f"alias/${{{ROOT_STACK_NAME.title}}}/{alias_name}"),
                )
            elif alias_name.startswith("alias/aws") or alias_name.startswith("aws"):
                raise ValueError(f"Alias {alias_name} cannot start with alias/aws.")
            Alias(
                f"{self.logical_name}Alias",
                template=template,
                AliasName=alias_name,
                TargetKeyId=Ref(self.cfn_resource),
                Metadata=metadata,
            )


class XStack(ComposeXStack):
    """
    Class for KMS Root stack
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, KmsKey, RES_KEY)
        stack_template = create_kms_template(settings)
        super().__init__(title, stack_template, **kwargs)
