# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from troposphere import Template
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack
    from .sqs_stack import Queue

from itertools import chain

import boto3.session
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import MAX_OUTPUTS, AccountId, GetAtt, Ref, Sub
from troposphere.sqs import Queue as CfnQueue
from troposphere.sqs import QueuePolicy

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resources_import import import_record_properties
from ecs_composex.sqs.sqs_params import SQS_ARN

from ..common.troposphere_tools import add_outputs, add_resource, build_template


def add_queue_default_policy(queue: Queue):
    queue_policy_title = f"{queue.logical_name}Policy"
    queue.resource_policy = QueuePolicy(
        queue_policy_title,
        PolicyDocument={
            "Version": "2008-10-17",
            "Id": "__default_policy",
            "Statement": [
                {
                    "Sid": "__owner_statement",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": Sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:root")
                    },
                    "Action": "sqs:*",
                    "Resource": GetAtt(queue.cfn_resource, SQS_ARN.return_value),
                }
            ],
        },
        Queues=[Ref(queue.cfn_resource)],
    )
    add_resource(queue.stack.stack_template, queue.resource_policy)


def define_queue_properties(queue):
    """
    Function to parse the queue definition and generate the queue accordingly. Created the redrive policy if necessary

    :param ecs_composex.common.compose_resources.Queue queue: name of the queue

    :return: queue
    :rtype: troposphere.sqs.Queue
    """

    name = set_else_none("QueueName", queue.properties)
    if keyisset("FifoQueue", queue.properties) and name and not name.endswith(".fifo"):
        queue.properties["QueueName"] = f"${name}.fifo"
        LOG.warning(
            f"QueueName was defined and FifoQueue set to true, but queue name was invalid. "
            f"Corrected to {queue.properties['QueueName']}"
        )
    props = import_record_properties(queue.properties, CfnQueue)
    queue.cfn_resource = CfnQueue(queue.logical_name, **props)
    LOG.debug(queue.cfn_resource.title, queue.logical_name)


def add_aws_services_queue_policy(queue: Queue):
    if not queue.resource_policy:
        return
    aws_services = set_else_none("AwsPrincipalsAccess", queue.parameters)
    publish_consume = set_else_none("PublishConsume", aws_services, alt_value=[])
    consume = [
        _elem
        for _elem in set_else_none("Consume", aws_services, alt_value=[])
        if _elem not in publish_consume
    ]
    publish = [
        _elem
        for _elem in set_else_none("Publish", aws_services, alt_value=[])
        if _elem not in publish_consume
    ]
    for service in chain(consume, publish, publish_consume):
        if service not in boto3.session.Session().get_available_services():
            raise ValueError(
                queue.module.res_key,
                queue.name,
                f"Service {service} is not valid. Valid services",
                boto3.session.Session().get_available_services(),
            )
    same_account_condition: dict = {"StringEquals": {"aws:SourceAccount": AccountId}}
    if consume:
        consume_statement = {
            "Sid": "__aws_services_consume",
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    Sub(f"{_aws_service}.${{AWS::URLSuffix}}")
                    for _aws_service in consume
                ]
            },
            "NotAction": [
                "sqs:TagQueue",
                "sqs:RemovePermission",
                "sqs:AddPermission",
                "sqs:UntagQueue",
                "sqs:PurgeQueue",
                "sqs:DeleteQueue",
                "sqs:CreateQueue",
                "sqs:SetQueueAttributes",
                "sqs:SendMessage",
            ],
            "Resource": GetAtt(queue.cfn_resource, SQS_ARN.return_value),
            "Condition": same_account_condition,
        }
        queue.resource_policy.PolicyDocument["Statement"].append(consume_statement)
    if publish:
        publish_statement = {
            "Sid": "__aws_services_publish",
            "Effect": "Allow",
            "Principal": {
                "Service": [
                    Sub(f"{_aws_service}.${{AWS::URLSuffix}}")
                    for _aws_service in publish
                ]
            },
            "Action": ["sqs:SendMessage"],
            "Resource": GetAtt(queue.cfn_resource, SQS_ARN.return_value),
            "Condition": same_account_condition,
        }
        queue.resource_policy.PolicyDocument["Statement"].append(publish_statement)

        if publish_consume:
            publish_consume_statement = {
                "Sid": "__aws_services_publish_consume",
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        Sub(f"{_aws_service}.${{AWS::URLSuffix}}")
                        for _aws_service in publish_consume
                    ]
                },
                "NotAction": [
                    "sqs:TagQueue",
                    "sqs:RemovePermission",
                    "sqs:AddPermission",
                    "sqs:UntagQueue",
                    "sqs:PurgeQueue",
                    "sqs:DeleteQueue",
                    "sqs:CreateQueue",
                    "sqs:SetQueueAttributes",
                ],
                "Resource": GetAtt(queue.cfn_resource, SQS_ARN.return_value),
                "Condition": same_account_condition,
            }
            queue.resource_policy.PolicyDocument["Statement"].append(
                publish_consume_statement
            )


def render_new_queues(
    settings: ComposeXSettings,
    new_queues: list[Queue],
    xstack: ComposeXStack,
    template: Template,
):
    """
    Sets the new SQS Queue properties. In case there are so many queues that there would not be enough outputs,
    split into 1 stack per queue

    :param settings:
    :param new_queues:
    :param xstack:
    :param template:
    """
    mono_template = False
    output_per_resource = 3
    if (len(new_queues) * output_per_resource) <= MAX_OUTPUTS:
        mono_template = True

    for queue in new_queues:
        queue.stack = xstack
        define_queue_properties(queue)
        if not queue.cfn_resource:
            continue
        queue.init_outputs()
        queue.generate_outputs()
        if mono_template:
            the_template = template
            queue.stack = xstack
        else:
            the_template = build_template(
                f"Template for SQS queue {queue.cfn_resource.title}",
            )
            queue.stack = ComposeXStack(queue.logical_name, stack_template=the_template)
            add_resource(template, queue.stack)
        add_resource(the_template, queue.cfn_resource)
        add_outputs(the_template, queue.outputs)
        add_queue_default_policy(queue)
        if queue.parameters and keyisset("AwsPrincipalsAccess", queue.parameters):
            add_aws_services_queue_policy(queue)
