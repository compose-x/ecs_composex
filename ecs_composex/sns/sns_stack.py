#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re

from botocore.exceptions import ClientError
from compose_x_common.aws.sns import SNS_TOPIC_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.sns import Topic as CfnTopic

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.compose_resources import XResource
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.sns.sns_params import (
    MOD_KEY,
    RES_KEY,
    TOPIC_ARN,
    TOPIC_KMS_KEY,
    TOPIC_NAME,
)
from ecs_composex.sns.sns_templates import generate_sns_templates
from ecs_composex.sqs.sqs_params import RES_KEY as SQS_KEY

LOG = setup_logging()


def get_topic_config(topic, account_id, resource_id):
    """
    Function to create the mapping definition for SNS topics

    :param Topic topic:
    :param str account_id: the 12 digits account ID
    :param str resource_id: the topic name
    :return:
    """

    topic_config = {TOPIC_NAME.return_value: resource_id}
    client = topic.lookup_session.client("sns")
    attributes_mapping = {
        TOPIC_ARN.title: "Attributes::TopicArn",
        TOPIC_KMS_KEY.return_value: "Attributes::KmsMasterKeyId",
    }
    try:
        topic_r = client.get_topic_attributes(TopicArn=topic.arn)
        attributes = attributes_to_mapping(topic_r, attributes_mapping)
        if keyisset(TOPIC_KMS_KEY.return_value, attributes) and not attributes[
            TOPIC_KMS_KEY.return_value
        ].startswith("arn:aws"):
            if attributes[TOPIC_KMS_KEY.return_value].startswith("alias/aws"):
                LOG.warning(
                    f"{topic.module_name}.{topic.name} - Topic uses the default AWS CMK."
                )
            else:
                LOG.warning(
                    f"{topic.module_name}.{topic.name} - KMS Key provided is not a valid ARN."
                )
            del attributes[TOPIC_KMS_KEY.return_value]
        topic_config.update(attributes)
        return topic_config
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def create_sns_mappings(resources, settings):
    if not keyisset(RES_KEY, settings.mappings):
        mappings = {}
        settings.mappings[RES_KEY] = mappings
    else:
        mappings = settings.mappings[RES_KEY]
    for resource in resources:
        resource.lookup_resource(
            SNS_TOPIC_ARN_RE, get_topic_config, CfnTopic.resource_type, "sns"
        )
        mappings.update({resource.logical_name: resource.mappings})


class Topic(XResource):
    """
    Class for SNS Topics
    """

    policies_scaffolds = get_access_types(MOD_KEY)
    keyword = "Topics"

    def init_outputs(self):
        self.output_properties = {
            TOPIC_ARN: (self.logical_name, self.cfn_resource, Ref, None),
            TOPIC_NAME: (
                f"{self.logical_name}{TOPIC_NAME.title}",
                self.cfn_resource,
                GetAtt,
                TOPIC_NAME.return_value,
            ),
        }


class Subscription(XResource):
    """
    Class for SNS Subscriptions
    """

    keyword = "Subscriptions"


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(self, title, settings, **kwargs):
        topics = []
        subscriptions = []
        if keyisset(Topic.keyword, settings.compose_content[RES_KEY]):
            for resource_name in settings.compose_content[RES_KEY][Topic.keyword]:
                topic = Topic(
                    resource_name,
                    settings.compose_content[RES_KEY][Topic.keyword][resource_name],
                    MOD_KEY,
                    settings,
                )
                settings.compose_content[RES_KEY][Topic.keyword][resource_name] = topic
                topics.append(topic)

        if keyisset(Subscription.keyword, settings.compose_content[RES_KEY]):
            for resource_name in settings.compose_content[RES_KEY][
                Subscription.keyword
            ]:
                subscription = Subscription(
                    resource_name,
                    settings.compose_content[RES_KEY][Subscription.keyword][
                        resource_name
                    ],
                    MOD_KEY,
                    settings,
                )
                settings.compose_content[RES_KEY][Subscription.keyword][
                    resource_name
                ] = subscription
                subscriptions.append(subscription)

        new_topics = [topic for topic in topics if not topic.lookup and not topic.use]
        new_subscriptions = [
            subscription
            for subscription in subscriptions
            if not subscription.lookup and not subscription.use
        ]
        if not new_topics and not new_subscriptions:
            self.is_void = True
        else:
            template = build_template(
                "Root template for SNS generated by ECS Compose-X"
            )
            generate_sns_templates(
                settings, new_topics, new_subscriptions, self, template
            )
            super().__init__(title, stack_template=template, **kwargs)
        for topic in topics:
            topic.stack = self
        for subscription in subscriptions:
            subscription.stack = self
        lookup_topics = [
            topic for topic in topics if topic.lookup and not topic.properties
        ]
        if lookup_topics:
            create_sns_mappings(lookup_topics, settings)

    def handle_sqs(self, root_template, sqs_root_stack):
        """
        Function to handle the SQS configuration to allow SNS to send messages to queues.
        """

    def add_xdependencies(self, root_stack, settings):
        """
        Method to add a dependencies from other X-Resources
        :param ComposeXStack root_stack: The ComposeX Root template
        :param ecs_composex.common.ComposeXSettings settings:
        """
        resources = root_stack.stack_template.resources
        sqs_res = SQS_KEY.strip("x-") if SQS_KEY.startswith("x-") else SQS_KEY
        if SQS_KEY in settings.compose_content and sqs_res in resources:
            self.DependsOn.append(sqs_res)
            self.handle_sqs(root_stack.stack_template, resources[sqs_res])
