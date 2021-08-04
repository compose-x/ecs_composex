#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to add topics and subscriptions to the SNS stack
"""

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere.sns import Subscription, Topic

from ecs_composex.common import LOG
from ecs_composex.common.outputs import get_import_value
from ecs_composex.sns import metadata
from ecs_composex.sqs.sqs_params import RES_KEY as SQS_KEY
from ecs_composex.sqs.sqs_params import SQS_ARN_T

TOPICS_KEY = "Topics"
SUBSCRIPTIONS_KEY = "Subscription"
TOPICS_STACK_NAME = "topics"
ENDPOINT_KEY = "Endpoint"
PROTOCOL_KEY = "Protocol"


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
    Function that builds the SNS topic template from cli.Dockerfile Properties

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
    topic.generate_outputs()


def add_topics_to_template(template, topics, content):
    """
    Function to interate over the topics and add them to the CFN Template

    :param troposphere.Template template:
    :param dict topics:
    :param dict content: Content of the compose file
    """
    for topic in topics:
        define_topic(topic, content)
        topic.init_outputs()
        topic.generate_outputs()
        template.add_resource(topic.cfn_resource)
        template.add_output(topic.outputs)


def add_sns_topics(root_template, new_topics, content):
    """
    Function to add SNS topics to the root template

    :param troposphere.Template root_template:
    :param dict content:
    :return:
    """
    add_topics_to_template(root_template, new_topics, content)


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


def generate_sns_templates(
    settings, new_topics, new_subscriptions, xstack, root_template
):
    """
    Entrypoint function to generate the SNS topics templates

    :param settings:
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return:
    """
    if new_topics:
        add_sns_topics(root_template, new_topics, settings.compose_content)
    return root_template
