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


from troposphere import AWS_PARTITION, AWS_ACCOUNT_ID
from troposphere import Sub, Ref, GetAtt, If
from troposphere.kms import Key, Alias

from ecs_composex.common import LOG, keyisset, build_template, NONALPHANUM
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kms import metadata
from ecs_composex.kms.kms_params import (
    RES_KEY,
    KMS_KEY_ID_T,
    KMS_KEY_ARN_T,
)

CFN_MAX_OUTPUTS = 50


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


def generate_key(key_name, res_name, key_def):
    """
    Function to create the KMS Key

    :param key_name:
    :param res_name:
    :param key_def:
    :return: key
    :rtype: troposphere.kms.Key
    """
    properties = (
        key_def["Properties"]
        if keyisset("Properties", key_def)
        else {
            "Description": Sub(f"{key_name} created in ${{{ROOT_STACK_NAME.title}}}"),
            "Enabled": True,
            "EnableKeyRotation": True,
            "KeyUsage": "ENCRYPT_DECRYPT",
            "PendingWindowInDays": 7,
        }
    )
    if not keyisset("KeyPolicy", properties):
        properties.update({"KeyPolicy": define_default_key_policy()})
    properties.update({"Metadata": metadata})
    LOG.debug(properties)
    kms_key = Key(res_name, **properties)
    return kms_key


def handle_key_settings(template, key, key_def):
    """
    Function to add to the template for additional KMS key related resources.

    :param troposphere.Template template:
    :param key: the KMS key
    :param dict key_def:
    :return:
    """
    if keyisset("Settings", key_def) and keyisset("Alias", key_def["Settings"]):
        alias_name = key_def["Settings"]["Alias"]
        if not (alias_name.startswith("alias/") or alias_name.startswith("aws")):
            alias_name = If(
                USE_STACK_NAME_CON_T,
                Sub(f"alias/${{AWS::StackName}}/{alias_name}"),
                Sub(f"alias/${{{ROOT_STACK_NAME.title}}}/{alias_name}"),
            )
        elif alias_name.startswith("alias/aws") or alias_name.startswith("aws"):
            raise ValueError(f"Alias {alias_name} cannot start with alias/aws.")
        Alias(
            f"{key.title}Alias",
            template=template,
            AliasName=alias_name,
            TargetKeyId=Ref(key),
            Metadata=metadata,
        )


def create_kms_template(settings):
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    mono_template = False
    template = build_template("Root template for KMS")
    if not keyisset(RES_KEY, settings.compose_content):
        return
    keys = settings.compose_content[RES_KEY]
    if len(list(keys.keys())) <= CFN_MAX_OUTPUTS:
        mono_template = True

    for key_name in keys:
        key_res_name = NONALPHANUM.sub("", key_name)
        key = generate_key(key_name, key_res_name, keys[key_name])
        if key:
            values = [
                (KMS_KEY_ARN_T, "Arn", GetAtt(key, "Arn")),
                (KMS_KEY_ID_T, "Name", Ref(key)),
            ]
            outputs = ComposeXOutput(key, values, True)
            if mono_template:
                template.add_resource(key)
                handle_key_settings(template, key, keys[key_name])
                template.add_output(outputs.outputs)
            elif not mono_template:
                key_template = build_template(f"Template for DynamoDB key {key.title}")
                key_template.add_resource(key)
                key_template.add_output(outputs.outputs)
                key_stack = ComposeXStack(key_res_name, stack_template=key_template)
                template.add_resource(key_stack)
    return template
