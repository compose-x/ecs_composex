#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
File to manage sqs to sqs dependency for dead letter queue
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

    from .sqs_stack import Queue

from troposphere import GetAtt, Ref

from ecs_composex.sqs.sqs_params import SQS_ARN

from ..common.troposphere_tools import add_parameters, add_update_mapping


def update_target_queue_pointer(
    queue: Queue, source_queue: Queue, settings: ComposeXSettings
) -> None:
    """
    Updates the ``deadLetterTargetArn`` of redrive policy with the appropriate Queue ARN
    """
    queue_id = queue.attributes_outputs[SQS_ARN]
    if queue.stack != source_queue.stack and queue.cfn_resource:
        add_parameters(source_queue.stack.stack_template, [queue_id["ImportParameter"]])
        source_queue.stack.Parameters.update(
            {queue_id["ImportParameter"].title: queue_id["ImportValue"]}
        )
        setattr(
            source_queue.cfn_resource.RedrivePolicy,
            "deadLetterTargetArn",
            Ref(queue_id["ImportParameter"]),
        )
    elif queue.stack == source_queue.stack:
        setattr(
            source_queue.cfn_resource.RedrivePolicy,
            "deadLetterTargetArn",
            GetAtt(queue.cfn_resource, SQS_ARN.return_value),
        )
    else:
        add_update_mapping(
            source_queue.stack.stack_template,
            queue.module.mapping_key,
            settings.mappings[queue.module.mapping_key],
        )
        setattr(
            source_queue.cfn_resource.RedrivePolicy,
            "deadLetterTargetArn",
            queue_id["ImportValue"],
        )


def sqs_to_sqs(queue: Queue, source_queue: Queue, settings: ComposeXSettings) -> None:
    """

    :param queue:
    :param source_queue: The queue with redrive policy
    :param settings:
    """
    if not source_queue.cfn_resource:
        return
    redrive_policy = (
        getattr(source_queue.cfn_resource, "RedrivePolicy")
        if hasattr(source_queue.cfn_resource, "RedrivePolicy")
        else None
    )
    if not redrive_policy:
        return
    if not hasattr(redrive_policy, "deadLetterTargetArn"):
        raise AttributeError(
            source_queue.module.res_key,
            source_queue.name,
            "RedrivePolicy does not have deadLetterTargetArn defined",
        )
    if not isinstance(redrive_policy.deadLetterTargetArn, str) or (
        isinstance(redrive_policy.deadLetterTargetArn, str)
        and not redrive_policy.deadLetterTargetArn.startswith(queue.module.res_key)
    ):
        return

    target_queue_name = redrive_policy.deadLetterTargetArn.split(
        f"{queue.module.res_key}::"
    )[-1]
    if target_queue_name == queue.name:
        update_target_queue_pointer(queue, source_queue, settings)
