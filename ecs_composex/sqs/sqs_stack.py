#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for the XStack SQS
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from botocore.exceptions import ClientError
from compose_x_common.aws.sqs import SQS_QUEUE_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref
from troposphere.sqs import Queue as CfnQueue

from ecs_composex.common import add_update_mapping, build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.sqs.sqs_ecs_scaling import handle_service_scaling
from ecs_composex.sqs.sqs_params import (
    SQS_ARN,
    SQS_KMS_KEY,
    SQS_NAME,
    SQS_URL,
    TAGGING_API_ID,
)
from ecs_composex.sqs.sqs_template import render_new_queues

LOG = setup_logging()


def get_queue_config(queue, account_id, resource_id):
    """

    :param ecs_composex.sqs.sqs_stack.Queue queue:
    :param account_id:
    :param resource_id:
    :return:
    """
    queue_config = {SQS_NAME: resource_id}
    client = queue.lookup_session.client("sqs")
    try:
        queue_config[SQS_URL] = client.get_queue_url(
            QueueName=resource_id, QueueOwnerAWSAccountId=account_id
        )["QueueUrl"]
        try:
            encryption_config_r = client.get_queue_attributes(
                QueueUrl=queue_config[SQS_URL],
                AttributeNames=["KmsMasterKeyId", "QueueArn"],
            )
            queue_config[SQS_ARN] = encryption_config_r["Attributes"]["QueueArn"]
            if keyisset("Attributes", encryption_config_r) and keyisset(
                "KmsMasterKeyId", encryption_config_r["Attributes"]
            ):
                kms_key_id = encryption_config_r["Attributes"]["KmsMasterKeyId"]
                if kms_key_id.startswith("arn:aws"):
                    queue_config[SQS_KMS_KEY] = encryption_config_r["Attributes"][
                        "KmsMasterKeyId"
                    ]
                else:
                    LOG.warning(
                        "The KMS Key provided is not an ARN. Implementation requires full ARN today"
                    )
            else:
                LOG.info(f"{queue.module.res_key}.{queue.name} - No KMS encryption.")
        except client.exceptions.InvalidAttributeName as error:
            LOG.error("Failed to retrieve the Queue attributes")
            LOG.error(error)
        return queue_config
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


class Queue(ApiXResource):
    """
    Class to represent a SQS Queue
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.kms_arn_attr = SQS_KMS_KEY
        self.arn_parameter = SQS_ARN
        self.ref_parameter = SQS_URL
        self.predefined_resource_service_scaling_function = handle_service_scaling

    def init_outputs(self):
        """
        Init output properties for a new resource
        """
        self.output_properties = {
            SQS_URL: (self.logical_name, self.cfn_resource, Ref, None, "Url"),
            SQS_ARN: (
                f"{self.logical_name}{SQS_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                SQS_ARN.return_value,
                "Arn",
            ),
            SQS_NAME: (
                f"{self.logical_name}{SQS_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                SQS_NAME.return_value,
                "QueueName",
            ),
        }


def resolve_lookup(
    lookup_resources, settings: ComposeXSettings, module: XResourceModule
) -> None:
    """
    Lookup AWS Resource

    :param list[Queue] lookup_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param XResourceModule module:
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            SQS_QUEUE_ARN_RE,
            get_queue_config,
            CfnQueue.resource_type,
            TAGGING_API_ID,
        )
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )
        LOG.info(
            f"{module.res_key}.{resource.name} - Matched AWS Resource {resource.arn}"
        )
        if keyisset(SQS_KMS_KEY, resource.lookup_properties):
            LOG.info(
                f"{module.res_key}.{resource.name} - Identified CMK - {resource.lookup_properties[SQS_KMS_KEY]}"
            )


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        """
        :param str title: Name of the stack
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        set_resources(settings, Queue, module)
        x_resources = settings.compose_content[module.res_key].values()
        lookup_resources = set_lookup_resources(x_resources)
        if lookup_resources:
            resolve_lookup(lookup_resources, settings, module)
        new_resources = set_new_resources(x_resources, True)
        if new_resources:
            template = build_template("SQS template generated by ECS Compose-X")
            if lookup_resources:
                add_update_mapping(
                    template, module.mapping_key, settings.mappings[module.mapping_key]
                )
            super().__init__(title, stack_template=template, **kwargs)
            render_new_queues(settings, new_resources, x_resources, self, template)
        else:
            self.is_void = True
        for resource in settings.compose_content[module.res_key].values():
            resource.stack = self
