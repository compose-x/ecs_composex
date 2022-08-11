#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Manages updating the S3 notifications to new x-sqs queues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sqs_stack import Queue
    from ecs_composex.s3.s3_bucket import Bucket
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.common.settings import ComposeXSettings

from compose_x_common.compose_x_common import keyisset
from troposphere import AccountId, GetAtt, Ref, Sub
from troposphere.s3 import QueueConfigurations
from troposphere.sqs import QueuePolicy

from ecs_composex.common.logging import LOG
from ecs_composex.sqs.sqs_params import SQS_ARN

from ..common.troposphere_tools import add_parameters, add_resource, build_template


def add_queue_policy(queue: Queue):
    s3_notifications_sid = "__s3_notifications"
    queue_policy_title = f"{queue.logical_name}Policy"
    if queue_policy_title in queue.stack.stack_template.resources:
        queue_policy = queue.stack.stack_template.resources[queue_policy_title]
    else:
        queue_policy = QueuePolicy(
            queue_policy_title,
            PolicyDocument={
                "Version": "2008-10-17",
                "Id": "__default_policy_ID",
                "Statement": [
                    {
                        "Sid": "__owner_statement",
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": Sub(
                                "arn:${AWS::Partition}:iam::${AWS::AccountId}:root"
                            )
                        },
                        "Action": "sqs:*",
                        "Resource": GetAtt(queue.cfn_resource, SQS_ARN.return_value),
                    }
                ],
            },
            Queues=[Ref(queue.cfn_resource)],
        )
        add_resource(queue.stack.stack_template, queue_policy)
    statements = queue_policy.PolicyDocument["Statement"]
    for statement in statements:
        if keyisset("Sid", statement) and statement["Sid"] == s3_notifications_sid:
            break
    else:
        statements.append(
            {
                "Sid": s3_notifications_sid,
                "Effect": "Allow",
                "Principal": {"Service": Sub("s3.${AWS::URLSuffix}")},
                "Action": ["sqs:SendMessage"],
                "Resource": GetAtt(queue.cfn_resource, SQS_ARN.return_value),
                "Condition": {"StringEquals": {"aws:SourceAccount": AccountId}},
            }
        )


def map_queue_with_bucket_notification(
    queue: Queue,
    bucket: Bucket,
    queue_notification: QueueConfigurations,
    settings: ComposeXSettings,
) -> None:
    """
    Maps the queue to the `Queue` queue_notification property

    :param queue:
    :param bucket:
    :param queue_notification:
    :param settings:
    """
    queue_id = queue.attributes_outputs[SQS_ARN]
    add_parameters(bucket.stack.stack_template, [queue_id["ImportParameter"]])
    bucket.stack.Parameters.update(
        {queue_id["ImportParameter"].title: queue_id["ImportValue"]}
    )
    setattr(queue_notification, "Queue", Ref(queue_id["ImportParameter"]))
    add_queue_policy(queue)


def update_new_bucket_properties(
    queue: Queue, bucket: Bucket, settings: ComposeXSettings
) -> None:
    if not hasattr(bucket.cfn_resource, "NotificationConfiguration"):
        return
    if not hasattr(
        bucket.cfn_resource.NotificationConfiguration, "QueueConfigurations"
    ):
        return
    queue_notifications = getattr(
        bucket.cfn_resource.NotificationConfiguration, "QueueConfigurations"
    )
    if not isinstance(queue_notifications, list):
        return

    for queue_notification in queue_notifications:
        if not isinstance(queue_notification, QueueConfigurations):
            raise TypeError(
                bucket.module.res_key,
                bucket.name,
                "Queue notification is not valid. Got",
                type(queue_notification),
                "expected",
                QueueConfigurations,
            )
        if not isinstance(queue_notification.Queue, str):
            continue
        if not queue_notification.Queue.startswith(queue.module.res_key):
            continue
        x_sqs = queue_notification.Queue.split(f"{queue.module.res_key}::")[-1]
        if x_sqs == queue.name:
            map_queue_with_bucket_notification(
                queue, bucket, queue_notification, settings
            )


def s3_to_sqs_notifications(
    queue: Queue,
    bucket: Bucket,
    settings: ComposeXSettings,
) -> None:
    """
    Updates the notification `Queue` property it is the x-sqs queue

    :param queue:
    :param bucket:
    :param settings:
    """
    if queue.cfn_resource and hasattr(queue.cfn_resource, "FifoQueue"):
        if queue.cfn_resource.FifoQueue is True:
            LOG.error(
                f"{queue.module.res_key}.{queue.name} is a Fifo Queue. "
                "These are not allowed for S3 notifications"
            )
            return
    if bucket.cfn_resource:
        update_new_bucket_properties(queue, bucket, settings)
    else:
        LOG.warning(
            f"{bucket.module.res_key}.{bucket.name} is not a new bucket. "
            f"Only granting S3 access in {queue.module.res_key}.{queue.name} policy"
        )
        add_queue_policy(queue)
