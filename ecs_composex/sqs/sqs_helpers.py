#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule
    from .sqs_stack import Queue

from botocore.exceptions import ClientError
from compose_x_common.aws.sqs import SQS_QUEUE_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere.sqs import Queue as CfnQueue

from ecs_composex.common.logging import LOG
from ecs_composex.sqs.sqs_params import (
    SQS_ARN,
    SQS_KMS_KEY,
    SQS_NAME,
    SQS_URL,
    TAGGING_API_ID,
)


def get_queue_config(queue: Queue, account_id: str, resource_id: str) -> dict | None:
    """

    :param ecs_composex.sqs.sqs_stack.Queue queue:
    :param str account_id:
    :param str resource_id:
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
                        "The KMS Key provided is not an ARN."
                        " Implementation requires full ARN today"
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


def resolve_lookup(
    lookup_resources: list[Queue], settings: ComposeXSettings, module: XResourceModule
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
                f"{module.res_key}.{resource.name} - Identified CMK"
                " - {resource.lookup_properties[SQS_KMS_KEY]}"
            )
