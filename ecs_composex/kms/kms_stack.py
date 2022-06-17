# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Manage Creation/Deletion of AWS KMS Keys
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from botocore.exceptions import ClientError
from compose_x_common.aws.kms import KMS_KEY_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, GetAtt, Ref, Sub
from troposphere.kms import Alias, Key

from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream
from ecs_composex.kms import metadata
from ecs_composex.kms.kms_ecs_cluster import handle_ecs_cluster
from ecs_composex.kms.kms_kinesis_firehose import kms_to_firehose
from ecs_composex.kms.kms_params import KMS_KEY_ALIAS_NAME, KMS_KEY_ARN, KMS_KEY_ID
from ecs_composex.kms.kms_s3 import handle_bucket_kms
from ecs_composex.kms.kms_sqs import handle_queue_kms
from ecs_composex.kms.kms_template import create_kms_template
from ecs_composex.resources_import import import_record_properties
from ecs_composex.s3.s3_bucket import Bucket
from ecs_composex.sqs.sqs_stack import Queue


def get_key_config(key, account_id: str, resource_id: str) -> dict | None:
    """

    :param KmsKey key:
    :param str account_id: unused
    :param str resource_id: unused
    :return:
    """
    key_attributes_mappings = {
        KMS_KEY_ARN: "KeyMetadata::Arn",
        KMS_KEY_ID: "KeyMetadata::KeyId",
    }
    client = key.lookup_session.client("kms")
    try:
        key_desc = client.describe_key(KeyId=key.arn)
        key_attributes = attributes_to_mapping(key_desc, key_attributes_mappings)
        key.manager = key_desc["KeyMetadata"]["KeyManager"]
        try:
            aliases_r = client.list_aliases(KeyId=key_attributes[KMS_KEY_ID])
            if aliases_r["Aliases"]:
                key_attributes[KMS_KEY_ALIAS_NAME] = aliases_r["Aliases"][0][
                    "AliasName"
                ]
        except client.exceptions.NotFoundException:
            LOG.debug(f"{key.module.res_key}.{key.name} - No KMS Key Alias.")
        return key_attributes
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def define_default_key_policy() -> dict:
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


class KmsKey(AwsEnvironmentResource, ApiXResource):
    """
    Class to represent a KMS Key
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        self.manager = "CUSTOMER"
        super().__init__(name, definition, module, settings)
        self.arn_parameter = KMS_KEY_ARN
        self.ref_parameter = KMS_KEY_ID
        self.support_defaults = True

    @property
    def is_cmk(self):
        if self.manager == "CUSTOMER":
            return True
        return False

    def init_outputs(self):
        self.output_properties = {
            KMS_KEY_ID: (
                f"{self.logical_name}{KMS_KEY_ID.title}",
                self.cfn_resource,
                Ref,
                None,
            ),
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
        if self.parameters and keyisset("Alias", self.parameters):
            alias_name = self.parameters["Alias"]
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

    def handle_x_dependencies(self, settings, root_stack=None) -> None:
        """
        WIll go over all the new resources to create in the execution and search for properties that can be updated
        with itself

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ComposeXStack root_stack: Not used. Present for general compatibility
        """
        handle_ecs_cluster(settings, self)
        for resource in settings.get_x_resources(include_mappings=False):
            if not resource.cfn_resource:
                continue
            if not resource.stack:
                LOG.debug(
                    f"resource {resource.name} has no `stack` attribute defined. Skipping"
                )
                continue
            mappings = [
                (Bucket, handle_bucket_kms),
                (Queue, handle_queue_kms),
                (DeliveryStream, kms_to_firehose),
            ]
            for target in mappings:
                if isinstance(resource, target[0]) or issubclass(
                    type(resource), target[0]
                ):
                    target[1](
                        self,
                        resource,
                        resource.stack,
                        settings,
                    )


class XStack(ComposeXStack):
    """
    Class for KMS Root stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):

        if module.new_resources:
            stack_template = build_template("Root template for KMS")
            super().__init__(title, stack_template, **kwargs)
            create_kms_template(stack_template, module.new_resources, self)
        else:
            self.is_void = True
        if module.lookup_resources:
            if not keyisset(module.mapping_key, settings.mappings):
                settings.mappings[module.mapping_key] = {}
            for resource in module.lookup_resources:
                resource.lookup_resource(
                    KMS_KEY_ARN_RE, get_key_config, Key.resource_type, "kms:key"
                )
                settings.mappings[module.mapping_key].update(
                    {resource.logical_name: resource.mappings}
                )
        for resource in module.resources_list:
            resource.stack = self
