#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to add topics and subscriptions to the SNS stack
"""

from troposphere import Ref
from troposphere.sns import Topic, Subscription

from ecs_composex.common import LOG, keyisset, keypresent, build_template
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.outputs import get_import_value
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.sns import metadata
from ecs_composex.sns.sns_params import RES_KEY, TOPIC_ARN_T
from ecs_composex.sqs.sqs_params import SQS_ARN_T, RES_KEY as SQS_KEY

TOPICS_KEY = "Topics"
SUBSCRIPTIONS_KEY = "Subscription"
TOPICS_STACK_NAME = "topics"
ENDPOINT_KEY = "Endpoint"
PROTOCOL_KEY = "Protocol"


def add_topics_outputs(template):
    """
    Function to add outputs to the template to export the Topics ARN

    :param troposphere.Template template:
    """
    resources = template.resources
    for resource_name in resources:
        resource = resources[resource_name]
        if isinstance(resource, Topic):
            template.add_output(
                ComposeXOutput(
                    resource, [(TOPIC_ARN_T, resource_name, Ref(resource))]
                ).outputs
            )


def check_queue_exists(queue_name, content):
    """
    Function to check

    :param str queue_name: Name of the queue defined in the subscription
    :param dict content: docker compose file content
    :return:
    """
    if keyisset(SQS_KEY, content):
        if not queue_name.startswith("arn:") and keyisset(queue_name, content[SQS_KEY]):
            return True
        elif queue_name.startswith("arn"):
            LOG.warning(
                f"Queue {queue_name} added as target, but not validated whether it exists"
            )
            return True
        else:
            LOG.error(f"Queue {queue_name} not defined in the {SQS_KEY} section")
            return False


def set_sqs_topic(subscription, content):
    """
    Function to set permissions and import for SQS subscription
    :return:
    """
    if keypresent(ENDPOINT_KEY, subscription) and not subscription[
        ENDPOINT_KEY
    ].startswith("arn:"):
        assert check_queue_exists(subscription[ENDPOINT_KEY], content)
    endpoint = (
        get_import_value(subscription[ENDPOINT_KEY], SQS_ARN_T)
        if not subscription[ENDPOINT_KEY].startswith("arn:")
        else subscription[ENDPOINT_KEY]
    )
    return Subscription(Protocol="sqs", Endpoint=endpoint)


def define_topic_subscriptions(subscriptions, content):
    """
    Function to define an SNS topic subscriptions

    :param list subscriptions: list of subscriptions as defined in the docker compose file
    :param dict content: docker compose file content
    :return:
    """
    required_keys = [ENDPOINT_KEY, PROTOCOL_KEY]
    subscriptions_objs = []
    for sub in subscriptions:
        LOG.debug(sub)
        if not all(key in sub for key in required_keys):
            raise AttributeError(
                "Required attributes for Subscription are",
                required_keys,
                "Provided",
                sub.keys(),
            )
        if keyisset(PROTOCOL_KEY, sub) and (
            sub[PROTOCOL_KEY] == "sqs" or sub[PROTOCOL_KEY] == "SQS"
        ):
            subscriptions_objs.append(set_sqs_topic(sub, content))
        else:
            subscriptions_objs.append(sub)
    return subscriptions_objs


def define_topic(topic, content):
    """
    Function that builds the SNS topic template from Dockerfile Properties

    :param topic: The topic and its definition
    :type topic: ecs_composex.sns.sns_stack.Topic
    """
    topic.cfn_resource = Topic(topic.logical_name, Metadata=metadata)
    if keyisset(SUBSCRIPTIONS_KEY, topic.properties):
        subscriptions = define_topic_subscriptions(
            topic.properties[SUBSCRIPTIONS_KEY], content
        )
        setattr(topic.cfn_resource, "Subscription", subscriptions)

        for key in topic.properties.keys():
            if type(topic.properties[key]) != list:
                setattr(topic.cfn_resource, key, topic.properties[key])
    return topic


def add_topics_to_template(template, topics, content):
    """
    Function to interate over the topics and add them to the CFN Template

    :param troposphere.Template template:
    :param dict topics:
    :param dict content: Content of the compose file
    """
    for topic_name in topics:
        define_topic(topics[topic_name], content)
        template.add_resource(topics[topic_name].cfn_resource)


def add_sns_topics(root_template, content, res_count, count=50):
    """
    Function to add SNS topics to the root template

    :param int count: quantity of resources that should trigger the split into nested stacks
    :param troposphere.Template root_template:
    :param dict content:
    :param int res_count: Number of resources created related to SNS
    :return:
    """
    if res_count > count:
        LOG.info(
            f"There are more than {count} resources to handle for SNS. Splitting into nested stacks"
        )
        template = build_template("Root stack for SNS topics")
        add_topics_to_template(template, content[RES_KEY][TOPICS_KEY], content)
        add_topics_outputs(template)
        root_template.add_resource(
            ComposeXStack(title=TOPICS_STACK_NAME, stack_template=template)
        )
    else:
        add_topics_to_template(root_template, content[RES_KEY][TOPICS_KEY], content)


def define_resources(res_content):
    """
    Function to determine how many resources are going to be created.
    :return:
    """
    res_count = 0
    if keyisset(TOPICS_KEY, res_content):
        for topic in res_content[TOPICS_KEY]:
            res_count += 1
            if keyisset("Subscription", topic):
                res_count += len(topic["Subscription"])
    if keyisset(SUBSCRIPTIONS_KEY, res_content):
        res_count += len(res_content[SUBSCRIPTIONS_KEY])
    return res_count


def generate_sns_templates(settings):
    """
    Entrypoint function to generate the SNS topics templates

    :param settings:
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return:
    """
    allowed_keys = [TOPICS_KEY, SUBSCRIPTIONS_KEY]
    res_content = settings.compose_content[RES_KEY]
    if not set(res_content).issubset(allowed_keys):
        raise KeyError(
            "SNS Only supports two types of resources",
            allowed_keys,
            "provided",
            res_content.keys(),
        )
    root_template = build_template("SNS Root Template")
    res_count = define_resources(res_content)
    if keyisset(TOPICS_KEY, res_content):
        add_sns_topics(root_template, settings.compose_content, res_count)
    if keyisset(SUBSCRIPTIONS_KEY, res_content):
        pass
    add_topics_outputs(root_template)
    return root_template
