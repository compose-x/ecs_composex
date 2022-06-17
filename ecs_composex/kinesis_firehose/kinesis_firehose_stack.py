# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle import/create AWS Kinesis Data Streams
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.mods_manager import ModManager

from botocore.exceptions import ClientError
from compose_x_common.aws.kinesis import KINESIS_FIREHOSE_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, NoValue, Ref
from troposphere.firehose import DeliveryStream as CfnDeliveryStream

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.iam.iam_stack import ResourceIamManager
from ecs_composex.kinesis_firehose.kinesis_firehose_params import (
    FIREHOSE_ARN,
    FIREHOSE_CMK_MANAGER,
    FIREHOSE_ID,
    FIREHOSE_KMS_KEY_ID,
)
from ecs_composex.kinesis_firehose.kinesis_firehose_template import (
    create_streams_template,
)
from ecs_composex.resource_settings import handle_resource_to_services


def get_delivery_stream_config(stream, account_id, resource_id):
    """
    Function to get the configuration of KMS Stream from API

    :param Stream stream:
    :param str account_id:
    :param str resource_id:
    :return:
    """
    client = stream.lookup_session.client("firehose")
    stream_mapping = {
        FIREHOSE_ARN: "DeliveryStreamARN",
        FIREHOSE_ID: "DeliveryStreamName",
        FIREHOSE_KMS_KEY_ID: "DeliveryStreamEncryptionConfiguration::KeyARN",
        FIREHOSE_CMK_MANAGER: "DeliveryStreamEncryptionConfiguration::KeyType",
    }
    try:
        stream_r = client.describe_delivery_stream(DeliveryStreamName=resource_id)
        stream_config = attributes_to_mapping(
            stream_r["DeliveryStreamDescription"], stream_mapping
        )
        return stream_config
    except client.exceptions.ResourceNotFoundException:
        return None
    except ClientError as error:
        LOG.error(error)


class DeliveryStream(AwsEnvironmentResource, ApiXResource):
    """
    Class to represent a KinesisFirehose DeliveryStream

    Both cloudcontrol and firehose discovery work.
    """

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        self.log_group = None
        super().__init__(
            name,
            definition,
            module,
            settings,
        )
        self.iam_manager = ResourceIamManager(self, "firehose")
        self.arn_parameter = FIREHOSE_ARN
        self.ref_parameter = FIREHOSE_ID
        self.cloud_control_attributes_mapping = {
            FIREHOSE_ARN: "Arn",
            FIREHOSE_ID: "DeliveryStreamName",
            FIREHOSE_KMS_KEY_ID: "DeliveryStreamEncryptionConfigurationInput::KeyARN",
            FIREHOSE_CMK_MANAGER: "DeliveryStreamEncryptionConfigurationInput::KeyType",
        }

    def init_outputs(self):
        self.output_properties = {
            FIREHOSE_ID: (self.logical_name, self.cfn_resource, Ref, None),
            FIREHOSE_ARN: (
                f"{self.logical_name}{FIREHOSE_ARN.title}",
                self.cfn_resource,
                GetAtt,
                FIREHOSE_ARN.return_value,
            ),
        }

    def to_ecs(
        self,
        settings: ComposeXSettings,
        modules: ModManager,
        root_stack: ComposeXStack = None,
        targets_overrides: list = None,
    ) -> None:
        """
        Maps API only based resource to ECS Services
        """
        if (
            hasattr(self.cfn_resource, "KinesisStreamSourceConfiguration")
            and self.cfn_resource.KinesisStreamSourceConfiguration != NoValue
        ):
            LOG.error(
                f"{self.module.res_key}.{self.name} - Source is Kinesis."
                " Grant access to the source stream instead."
            )
            return
        LOG.debug(f"{self.module.res_key}.{self.name} - Linking to services")
        handle_resource_to_services(
            settings,
            self,
            arn_parameter=self.arn_parameter,
            nested=False,
        )
        if self.predefined_resource_service_scaling_function:
            self.predefined_resource_service_scaling_function(self, settings)

    def ensure_iam_policies_dependencies(self):
        if not hasattr(self.cfn_resource, "DependsOn"):
            setattr(self.cfn_resource, "DependsOn", [])
        depends_on = getattr(self.cfn_resource, "DependsOn")
        for policy in self.iam_manager.iam_modules_policies.values():
            if policy.title not in depends_on:
                depends_on.append(policy.title)
                LOG.debug(f"Enforce {self.name} depends on {policy.title}")


def resolve_lookup(
    lookup_resources: list[DeliveryStream],
    settings: ComposeXSettings,
    module: XResourceModule,
) -> None:
    """
    Lookup AWS Kinesis streams and creates CFN Mappings
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        LOG.info(
            f"{resource.module.res_key}.{resource.logical_name} - Looking up AWS Resource"
        )
        resource.lookup_resource(
            KINESIS_FIREHOSE_ARN_RE,
            get_delivery_stream_config,
            CfnDeliveryStream.resource_type,
            "firehose:deliverystream",
        )
        LOG.info(f"{module.res_key}.{resource.name} - Matched to {resource.arn}")
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )


class XStack(ComposeXStack):
    """
    Class to represent Kinesis Data Streams stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)
        if module.new_resources:
            stack_template = create_streams_template(module.new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in module.resources_list:
            resource.stack = self
