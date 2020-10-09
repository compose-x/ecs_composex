# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Generates the individual SQS Queues templates."""

from copy import deepcopy

from troposphere import Sub, GetAtt, Ref
from troposphere.sqs import Queue, RedrivePolicy

from ecs_composex.common import (
    build_template,
    keyisset,
    keypresent,
    LOG,
    NONALPHANUM,
)
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.sqs import metadata
from ecs_composex.sqs.sqs_params import RES_KEY
from ecs_composex.sqs.sqs_params import (
    SQS_NAME_T,
    SQS_ARN_T,
    DLQ_ARN,
    DLQ_ARN_T,
    SQS_URL,
)

CFN_MAX_OUTPUTS = 50


def define_redrive_policy(target_queue, retries=None, mono_template=True):

    policy = {
        "RedrivePolicy": RedrivePolicy(
            deadLetterTargetArn=GetAtt(target_queue, "Arn")
            if mono_template
            else Ref(DLQ_ARN),
            maxReceiveCount=retries,
        )
    }
    return policy


def set_queue(queue, properties, redrive_policy=None):
    """
    Function to define and set the SQS Queue

    :param queue: Queue object
    :param dict properties: queue properties
    :param dict redrive_policy: redrive policy in case it has been defined

    :return: queue
    :rtype: troposphere.sqs.Queue
    """
    if redrive_policy is not None:
        properties.update(redrive_policy)
    if keyisset("QueueName", properties):
        properties.pop("QueueName")
        properties["QueueName"] = Sub(f"${{{ROOT_STACK_NAME_T}}}-{queue.name}")
        if keyisset("FifoQueue", properties):
            properties["QueueName"] = Sub(f"${{{ROOT_STACK_NAME_T}}}-{queue.name}.fifo")
    queue = Queue(queue.logical_name, **properties)
    return queue


def define_queue(queue, queues, mono_template=True):
    """
    Function to parse the queue definition and generate the queue accordingly. Created the redrive policy if necessary

    :param ecs_composex.common.compose_resources.Queue queue: name of the queue
    :param dict queues: the queues defined in x-sqs
    :param bool mono_template: whether or not there are so many outputs we need to split.

    :return: queue
    :rtype: troposphere.sqs.Queue
    """
    redrive_policy = None
    if keypresent("Properties", queue.definition):
        props = deepcopy(queue.definition)
        properties = props["Properties"]
        properties.update({"Metadata": metadata})
    else:
        properties = {"Metadata": metadata}
    if keyisset("RedrivePolicy", properties) and keyisset(
        "deadLetterTargetArn", properties["RedrivePolicy"]
    ):
        redrive_target = properties["RedrivePolicy"]["deadLetterTargetArn"]
        if redrive_target not in queues:
            raise KeyError(
                f"Queue {redrive_target} defined as DLQ for {queue.name} but is not defined"
            )
        if keyisset("maxReceiveCount", properties["RedrivePolicy"]):
            retries = int(properties["RedrivePolicy"]["maxReceiveCount"])
        else:
            retries = 5
        redrive_policy = define_redrive_policy(redrive_target, retries, mono_template)
    queue = set_queue(queue, properties, redrive_policy)
    LOG.debug(queue.title)
    return queue


def generate_sqs_root_template(settings):
    """
    Function to create the root DynamdoDB template.

    :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings.
    :return:
    """
    mono_template = False
    output_per_resource = 3
    if not keyisset(RES_KEY, settings.compose_content):
        return None

    queues = settings.compose_content[RES_KEY]
    if (len(list(queues.keys())) * output_per_resource) <= CFN_MAX_OUTPUTS:
        mono_template = True
    template = build_template("DynamoDB for ECS ComposeX")
    for queue_name in queues:
        queue = define_queue(queues[queue_name], queues, mono_template)
        if queue:
            values = [
                (SQS_URL, "Url", Ref(queue)),
                (SQS_ARN_T, SQS_ARN_T, GetAtt(queue, SQS_ARN_T)),
                (SQS_NAME_T, SQS_NAME_T, Ref(queue)),
            ]
            outputs = ComposeXOutput(queue, values, duplicate_attr=(not mono_template))
            if mono_template:
                template.add_resource(queue)
                template.add_output(outputs.outputs)
            elif not mono_template:
                parameters = {}
                if hasattr(queue, "RedrivePolicy"):
                    parameters.update(
                        {
                            DLQ_ARN_T: GetAtt(
                                NONALPHANUM.sub(
                                    "",
                                    queues[queue_name].definition["Properties"][
                                        "RedrivePolicy"
                                    ]["deadLetterTargetArn"],
                                ),
                                f"Outputs.{SQS_ARN_T}",
                            )
                        }
                    )
                queue_template = build_template(
                    f"Template for SQS queue {queue.title}", [DLQ_ARN]
                )
                queue_template.add_resource(queue)
                queue_template.add_output(outputs.outputs)
                queue_stack = ComposeXStack(
                    queues[queue_name].logical_name,
                    stack_template=queue_template,
                    stack_parameters=parameters,
                )
                template.add_resource(queue_stack)
    return template
