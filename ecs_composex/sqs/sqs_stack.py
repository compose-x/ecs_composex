#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for the XStack SQS
"""
import warnings

from botocore.exceptions import ClientError
from compose_x_common.aws.sqs import SQS_QUEUE_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref
from troposphere.sqs import Queue as CfnQueue

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.sqs.sqs_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
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
    queue_config = {SQS_NAME.return_value: resource_id}
    client = queue.lookup_session.client("sqs")
    try:
        queue_config[SQS_URL.title] = client.get_queue_url(
            QueueName=resource_id, QueueOwnerAWSAccountId=account_id
        )["QueueUrl"]
        try:
            encryption_config_r = client.get_queue_attributes(
                QueueUrl=queue_config[SQS_URL.title],
                AttributeNames=["KmsMasterKeyId", "QueueArn"],
            )
            queue_config[SQS_ARN.return_value] = encryption_config_r["Attributes"][
                "QueueArn"
            ]
            if keyisset("Attributes", encryption_config_r) and keyisset(
                "KmsMasterKeyId", encryption_config_r["Attributes"]
            ):
                kms_key_id = encryption_config_r["Attributes"]["KmsMasterKeyId"]
                if kms_key_id.startswith("arn:aws"):
                    queue_config[SQS_KMS_KEY.title] = encryption_config_r["Attributes"][
                        "KmsMasterKeyId"
                    ]
                else:
                    LOG.warning(
                        "The KMS Key provided is not an ARN. Implementation requires full ARN today"
                    )
            else:
                LOG.info(f"No KMS Key associated with {queue.name}")
        except client.exceptions.InvalidAttributeName as error:
            LOG.error("Failed to retrieve the Queue attributes")
            LOG.error(error)
        return queue_config
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


class Queue(XResource):
    """
    Class to represent a SQS Queue
    """

    policies_scaffolds = get_access_types(MOD_KEY)

    def init_outputs(self):
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


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Queue, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            template = build_template("Parent template for SQS in ECS Compose-X")
            super().__init__(title, stack_template=template, **kwargs)
            render_new_queues(settings, new_resources, self, template)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            for resource in lookup_resources:
                resource.lookup_resource(
                    SQS_QUEUE_ARN_RE,
                    get_queue_config,
                    CfnQueue.resource_type,
                    TAGGING_API_ID,
                )
                settings.mappings[RES_KEY].update(
                    {resource.logical_name: resource.mappings}
                )
                if keyisset(SQS_KMS_KEY.return_value, resource.mappings):
                    LOG.info(f"{RES_KEY}.{resource.name} - Identified CMK")
            if use_resources:
                warnings.warn("x-sqs.Use is not yet supported")

        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
