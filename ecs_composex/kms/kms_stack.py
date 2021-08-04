#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, GetAtt, If, Ref, Sub
from troposphere.kms import Alias, Key

from ecs_composex.common import LOG, build_template
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kms import metadata
from ecs_composex.kms.kms_params import KMS_KEY_ARN, KMS_KEY_ID, MOD_KEY, RES_KEY
from ecs_composex.kms.kms_perms import get_access_types
from ecs_composex.kms.kms_template import create_kms_template
from ecs_composex.resources_import import import_record_properties


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

    policies_scaffolds = get_access_types()

    def init_outputs(self):
        self.output_properties = {
            KMS_KEY_ID: (self.logical_name, self.cfn_resource, Ref, None),
            KMS_KEY_ARN: (
                f"{self.logical_name}{KMS_KEY_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                KMS_KEY_ARN.return_value,
            ),
        }

    def define_kms_key(self):
        """
        Method to set the KMS Key
        """
        if not self.properties:
            props = {
                "Description": Sub(
                    f"{self.name} created in ${{{ROOT_STACK_NAME.title}}}"
                ),
                "Enabled": True,
                "EnableKeyRotation": True,
                "KeyUsage": "ENCRYPT_DECRYPT",
                "PendingWindowInDays": 7,
            }
        else:
            props = import_record_properties(self.properties, Key)
        if not keyisset("KeyPolicy", props):
            props.update({"KeyPolicy": define_default_key_policy()})
        props.update({"Metadata": metadata})
        LOG.debug(props)
        self.cfn_resource = Key(self.logical_name, **props)

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
        set_resources(settings, KmsKey, RES_KEY, MOD_KEY)
        new_keys = [
            key
            for key in settings.compose_content[RES_KEY].values()
            if not key.lookup and not key.use
        ]
        if new_keys:
            stack_template = build_template("Root template for KMS")
            super().__init__(title, stack_template, **kwargs)
            create_kms_template(stack_template, new_keys, self)
        else:
            self.is_void = True
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
