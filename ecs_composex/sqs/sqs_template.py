# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>


from copy import deepcopy

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import GetAtt, Ref, Sub
from troposphere.sqs import Queue, RedrivePolicy

from ecs_composex.common import LOG, NONALPHANUM, build_template
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.sqs import metadata
from ecs_composex.sqs.sqs_params import DLQ_ARN, DLQ_ARN_T, SQS_ARN, SQS_ARN_T

CFN_MAX_OUTPUTS = 190


def define_redrive_policy(target_queue, retries=None, mono_template=True):
    if target_queue.cfn_resource:
        policy = {
            "RedrivePolicy": RedrivePolicy(
                deadLetterTargetArn=GetAtt(target_queue.cfn_resource, "Arn")
                if mono_template
                else Ref(DLQ_ARN),
                maxReceiveCount=retries,
            )
        }
    else:
        policy = {
            "RedrivePolicy": RedrivePolicy(
                deadLetterTargetArn=target_queue.attributes_outputs[SQS_ARN][
                    "ImportValue"
                ],
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
    name = None
    if redrive_policy is not None:
        properties.update(redrive_policy)
    if keyisset("QueueName", properties):
        name = properties["QueueName"]
        properties.pop("QueueName")
    if keyisset("FifoQueue", properties):
        properties["QueueName"] = (
            Sub(f"${{{ROOT_STACK_NAME_T}}}-{queue.name}.fifo")
            if not name
            else Sub(f"${{{ROOT_STACK_NAME_T}}}-{name}.fifo")
        )
    else:
        properties["QueueName"] = (
            Sub(f"${{{ROOT_STACK_NAME_T}}}-{queue.name}")
            if not name
            else Sub(f"${{{ROOT_STACK_NAME_T}}}-{name}")
        )
    queue = Queue(queue.logical_name, **properties)
    return queue


def define_queue(queue, queues, mono_template=True):
    """
    Function to parse the queue definition and generate the queue accordingly. Created the redrive policy if necessary

    :param ecs_composex.common.compose_resources.Queue queue: name of the queue
    :param list[ecs_composex.sqs.sqs_stack.Queue] queues: the queues defined in x-sqs
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
        for _queue in queues:
            if redrive_target == _queue.name:
                break
        else:
            raise KeyError(
                f"Queue {redrive_target} defined as DLQ for {queue.name} but is not defined"
            )
        if keyisset("maxReceiveCount", properties["RedrivePolicy"]):
            retries = int(properties["RedrivePolicy"]["maxReceiveCount"])
        else:
            retries = 5
        redrive_policy = define_redrive_policy(_queue, retries, mono_template)
    queue.cfn_resource = set_queue(queue, properties, redrive_policy)

    LOG.debug(queue.cfn_resource.title, queue.logical_name)
    return queue


def render_new_queues(settings, new_queues, queues, xstack, template):
    """
    Function to create the root DynamdoDB template.

    :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings.
    """
    mono_template = False
    output_per_resource = 3
    if (len(new_queues) * output_per_resource) <= CFN_MAX_OUTPUTS:
        mono_template = True

    for queue in new_queues:
        queue.stack = xstack
        define_queue(queue, queues, mono_template)
        if queue.cfn_resource:
            queue.init_outputs()
            queue.generate_outputs()
            if mono_template:
                template.add_resource(queue.cfn_resource)
                template.add_output(queue.outputs)
            elif not mono_template:
                parameters = {}
                if hasattr(queue, "RedrivePolicy"):
                    parameters.update(
                        {
                            DLQ_ARN_T: GetAtt(
                                NONALPHANUM.sub(
                                    "",
                                    queues[queue.name].definition["Properties"][
                                        "RedrivePolicy"
                                    ]["deadLetterTargetArn"],
                                ),
                                f"Outputs.{SQS_ARN_T}",
                            )
                        }
                    )
                queue_template = build_template(
                    f"Template for SQS queue {queue.cfn_resource.title}",
                    [DLQ_ARN],
                )
                queue_template.add_resource(queue.cfn_resource)
                queue_template.add_output(queue.outputs)
                queue_stack = ComposeXStack(
                    queue.logical_name,
                    stack_template=queue_template,
                    stack_parameters=parameters,
                )
                template.add_resource(queue_stack)
