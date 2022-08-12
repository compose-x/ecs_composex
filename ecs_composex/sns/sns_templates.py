# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to add topics and subscriptions to the SNS stack
"""

from compose_x_common.compose_x_common import keyisset
from troposphere.sns import Topic

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_outputs
from ecs_composex.sns import metadata

TOPICS_KEY = "Topics"
SUBSCRIPTIONS_KEY = "Subscription"
TOPICS_STACK_NAME = "topics"
ENDPOINT_KEY = "Endpoint"
PROTOCOL_KEY = "Protocol"


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
            pass
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
        add_outputs(template, topic.outputs)


def add_sns_topics(root_template, new_topics, content):
    """
    Function to add SNS topics to the root template

    :param troposphere.Template root_template:
    :param new_topics:
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


def generate_sns_templates(settings, new_topics, xstack, root_template):
    """
    Entrypoint function to generate the SNS topics templates

    :param settings:
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return:
    """
    if new_topics:
        add_sns_topics(root_template, new_topics, settings.compose_content)
    return root_template
