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

import boto3
from troposphere import Tags, Sub, GetAtt, If, Ref
from troposphere.sqs import Queue, RedrivePolicy
from troposphere.ssm import Parameter as SsmParameter

from ecs_composex.common import (
    build_template,
    cfn_params,
    keyisset,
    keypresent,
    LOG,
)
from ecs_composex.common import validate_kwargs
from ecs_composex.common.cfn_conditions import (
    USE_SSM_ONLY_T,
    USE_SSM_EXPORTS_T,
    USE_STACK_NAME_CON_T,
)
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.sqs.sqs_params import RES_KEY, SQS_SSM_PREFIX
from ecs_composex.sqs.sqs_params import (
    SQS_NAME_T,
    SQS_NAME,
    DLQ_NAME_T,
    DLQ_NAME,
    SQS_ARN_T,
    DLQ_ARN,
    DLQ_ARN_T,
)


def define_queue_tags(properties, queue_name):
    """
    Function to define the SQS Queue Tags

    :param properties: Properties imported from Compose File
    :type properties: dict
    :param queue_name: The Queue name as defined in ComposeX
    :type queue_name: str

    :returns: Tags()
    :rtype: troposphere.Tags
    """
    tag_name_exists = False
    if keyisset("Tags", properties):
        for key in properties["Tags"]:
            if key == "Name":
                tag_name_exists = True
    else:
        properties["Tags"] = {}

    if not tag_name_exists:
        properties["Tags"]["Name"] = queue_name
    return Tags(properties["Tags"])


def add_redrive_policy(queue_tpl, queue_name, properties, dlq_name):
    """
    Function to add a DLQ redrive policy to the SQS Queue

    :param queue_tpl: Template of the queue to add the redrive for
    :type queue_tpl: troposphere.Template
    :param queue_name: Name of the Queue as defined in ComposeX file
    :type queue_name: str
    :param properties: Queue properties as defined in ComposeX file
    :type properties: dict
    :param dlq_name: Name of the redrive queue as defined in ComposeX File
    :type dlq_name: str

    :returns: dict containing the RedrivePolicy
    :rtype: dict
    """
    ssm_string = (
        f"/${{{ROOT_STACK_NAME_T}}}{SQS_SSM_PREFIX}${{{DLQ_NAME_T}}}/{SQS_ARN_T}"
    )
    ssm_resolve = Sub(r"{{resolve:ssm:%s:1}}" % (ssm_string))
    # cfn_import = ImportValue(
    #     Sub(
    #         f"${{{ROOT_STACK_NAME_T}}}"
    #         f"{DELIM}"
    #         f"${{{DLQ_NAME_T}}}"
    #         f"{DELIM}"
    #         f"{SQS_ARN_T}"
    #     )
    # )
    redrive_queue_import = If(USE_SSM_ONLY_T, ssm_resolve, Ref(DLQ_ARN))
    queue_tpl.add_parameter(DLQ_ARN)
    queue_tpl.add_parameter(DLQ_NAME)
    policy = properties["RedrivePolicy"]
    policy["deadLetterTargetArn"] = redrive_queue_import
    policy_obj = RedrivePolicy(**policy)
    return {"RedrivePolicy": policy_obj}


def add_ssm_parameters(src_template, queue_obj):
    """
    Function to add SSM parameters to store Queue information

    :param src_template: Template to add the SSM params to
    :type src_template: troposphere.Template
    :param queue_obj: Queue to ref/getatt from
    :type queue_obj: troposphere.sqs.Queue
    """
    ssm_name_string = f"/${{{ROOT_STACK_NAME_T}}}{SQS_SSM_PREFIX}${{{SQS_NAME_T}}}"
    LOG.debug(ssm_name_string)
    SsmParameter(
        "QueueArnSsmParameter",
        template=src_template,
        Condition=USE_SSM_EXPORTS_T,
        DependsOn=[queue_obj],
        Name=Sub(f"{ssm_name_string}/{SQS_ARN_T}"),
        Value=GetAtt(queue_obj, "Arn"),
        Tier="Standard",
        Type="String",
    )
    SsmParameter(
        "QueueNameSsmParameter",
        template=src_template,
        Condition=USE_SSM_EXPORTS_T,
        DependsOn=[queue_obj],
        Name=Sub(f"{ssm_name_string}/{SQS_NAME_T}"),
        Value=GetAtt(queue_obj, "QueueName"),
        Tier="Standard",
        Type="String",
    )


def generate_queue_template(queue_name, properties, redrive_queue=None):
    """
    Function that generates a single queue template

    :param redrive_queue: SQS Redrive queue for DLQ
    :type redrive_queue: str
    :param queue_name: Name of the Queue as defined in ComposeX File
    :type queue_name: str
    :param properties: The queue properties
    :type properties: dict
    :param tags: tags to add to the queue
    :type tags: troposphere.Tags

    :returns: queue_template
    :rtype: troposphere.Template
    """
    if not queue_name:
        raise TypeError("Parameter queue_name must be a non-empty string")
    queue_template = build_template(
        f"Queue {queue_name} in {{{ROOT_STACK_NAME_T}}}", [SQS_NAME]
    )
    if redrive_queue is not None:
        properties.update(
            add_redrive_policy(queue_template, queue_name, properties, redrive_queue)
        )
    properties["Tags"] = define_queue_tags(properties, queue_name)
    if "QueueName" in properties.keys():
        properties.pop("QueueName")
        properties["QueueName"] = Sub(
            f"${{{ROOT_STACK_NAME_T}}}-${properties['QueueName']}"
        )
    else:
        properties["QueueName"] = Sub(f"${{{ROOT_STACK_NAME_T}}}-${{{SQS_NAME_T}}}")
    queue = Queue(queue_name, template=queue_template, **properties)
    add_ssm_parameters(queue_template, queue)
    queue_template.add_output(
        formatted_outputs(
            [
                {SQS_NAME_T: GetAtt(queue, SQS_NAME_T)},
                {SQS_ARN_T: GetAtt(queue, "Arn")},
            ],
            obj_name=SQS_NAME,
            export=True,
        )
    )
    return queue_template


def add_queue_stack(queue_name, queue, queues, session, **kwargs):
    """
    Function to define the Queue template settings for the Nested Stack

    :param tags: tags to add to the resources of the stack.
    :param queue_name: Name of the queue as defined in Docker ComposeX file
    :param queue: the queue
    :param queues: all the queues in a list
    :param session: session to override
    :param kwargs: optional arguments

    :return: Queue Stack object
    :rtype: ecs_composex.common.files.ComposeXStack
    """
    depends_on = []
    parameters = {
        SQS_NAME_T: queue_name,
        ROOT_STACK_NAME_T: If(
            USE_STACK_NAME_CON_T, Ref("AWS::StackName"), Ref(ROOT_STACK_NAME)
        ),
        cfn_params.USE_CFN_EXPORTS_T: Ref(cfn_params.USE_CFN_EXPORTS),
        cfn_params.USE_SSM_EXPORTS_T: Ref(cfn_params.USE_SSM_EXPORTS),
    }
    if keypresent("Properties", queue):
        properties = queue["Properties"]
    else:
        properties = {}
    if keyisset("RedrivePolicy", properties):
        redrive_target = properties["RedrivePolicy"]["deadLetterTargetArn"]
        if redrive_target not in queues:
            raise KeyError(
                f"Queue {redrive_target} defined as DLQ for {queue_name} but is not defined"
            )
        depends_on.append(redrive_target)
        parameters.update(
            {
                DLQ_ARN_T: GetAtt(redrive_target, f"Outputs.{SQS_ARN_T}"),
                DLQ_NAME_T: GetAtt(redrive_target, f"Outputs.{SQS_NAME_T}"),
            }
        )
        queue_tpl = generate_queue_template(queue_name, properties, redrive_target)
    else:
        queue_tpl = generate_queue_template(queue_name, properties)
    LOG.debug(parameters)
    LOG.debug(session)
    queue_stack = ComposeXStack(
        queue_name,
        stack_template=queue_tpl,
        Parameters=parameters,
        DependsOn=depends_on,
        **kwargs,
    )
    return queue_stack


def generate_sqs_root_template(compose_content, tags=None, session=None, **kwargs):
    """
    Generates a base template for a sqs queues. Iterates over each queue defined
    in x-sqs of the ComposeX file and identify settings and properties for these

    :param compose_content: The Docker compose content
    :type compose_content: dict
    :param session: boto3 session to override default
    :type session: boto3.session.Session

    :return: SQS Root/Parent template
    :rtype: troposphere.Template
    """
    if not session:
        session = boto3.session.Session()
    validate_kwargs(["BucketName"], kwargs)
    description = "Root SQS Template"
    if keyisset("EnvName", kwargs):
        description = f"Root SQS Template for {kwargs['EnvName']}"
    root_tpl = build_template(description)
    queues = compose_content[RES_KEY]
    for queue_name in queues:
        LOG.debug(queue_name)
        LOG.debug(session)
        queue_stack = add_queue_stack(
            queue_name, queues[queue_name], queues.keys(), session, **kwargs,
        )
        root_tpl.add_resource(queue_stack)
    return root_tpl
