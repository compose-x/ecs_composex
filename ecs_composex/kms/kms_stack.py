#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from botocore.exceptions import ClientError
from compose_x_common.aws.kms import KMS_KEY_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, GetAtt, Ref, Sub
from troposphere.kms import Alias, Key

from ecs_composex.common import LOG, build_template
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.kms import metadata
from ecs_composex.kms.kms_params import (
    KMS_KEY_ALIAS_NAME,
    KMS_KEY_ARN,
    KMS_KEY_ID,
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
)
from ecs_composex.kms.kms_template import create_kms_template
from ecs_composex.resources_import import import_record_properties


def get_key_config(key, account_id, resource_id):
    """

    :param Key key:
    :return:
    """
    key_attributes_mappings = {
        KMS_KEY_ARN.return_value: "KeyMetadata::Arn",
        KMS_KEY_ID.title: "KeyMetadata::KeyId",
    }
    client = key.lookup_session.client("kms")
    try:
        key_desc = client.describe_key(KeyId=key.arn)
        key_attributes = attributes_to_mapping(key_desc, key_attributes_mappings)
        try:
            aliases_r = client.list_aliases(KeyId=key_attributes[KMS_KEY_ID.title])
            key_attributes[KMS_KEY_ALIAS_NAME.title] = aliases_r["Aliases"][0][
                "AliasName"
            ]
        except client.exceptions.NotFoundException:
            LOG.debug(
                f"No alias was found for KMS Key {key_attributes[KMS_KEY_ID.title]}"
            )
        return key_attributes
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


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

    policies_scaffolds = get_access_types(MOD_KEY)

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
                    f"{self.name} created in ${{STACK_NAME}}",
                    STACK_NAME=define_stack_name(),
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
                alias_name = Sub(
                    f"alias/${{STACK_NAME}}/{alias_name}",
                    STACK_NAME=define_stack_name(template),
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
        set_resources(settings, KmsKey, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = build_template("Root template for KMS")
            super().__init__(title, stack_template, **kwargs)
            create_kms_template(stack_template, new_resources, self)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            for resource in lookup_resources:
                resource.lookup_resource(
                    KMS_KEY_ARN_RE, get_key_config, Key.resource_type, "kms:key"
                )
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
