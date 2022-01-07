#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from botocore.exceptions import ClientError
from compose_x_common.aws.sns import SNS_TOPIC_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.sns import Topic as CfnTopic

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import ApiXResource, XResource
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.sns.sns_params import (
    MAPPINGS_KEY,
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

    topic_config = {TOPIC_NAME: resource_id}
    client = topic.lookup_session.client("sns")
    attributes_mapping = {
        TOPIC_ARN: "Attributes::TopicArn",
        TOPIC_KMS_KEY: "Attributes::KmsMasterKeyId",
    }
    try:
        topic_r = client.get_topic_attributes(TopicArn=topic.arn)
        attributes = attributes_to_mapping(topic_r, attributes_mapping)
        if keyisset(TOPIC_KMS_KEY, attributes) and not attributes[
            TOPIC_KMS_KEY
        ].startswith("arn:aws"):
            if attributes[TOPIC_KMS_KEY].startswith("alias/aws"):
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
    """
    Creates the Mappings for x-sns

    :param list[Topic] resources:
    :param settings:
    :return:
    """
    if not keyisset(MAPPINGS_KEY, settings.mappings):
        settings.mappings[MAPPINGS_KEY] = {}
    for resource in resources:
        resource.lookup_resource(
            SNS_TOPIC_ARN_RE, get_topic_config, CfnTopic.resource_type, "sns"
        )
        settings.mappings[MAPPINGS_KEY].update(
            {resource.logical_name: resource.mappings}
        )


class Topic(ApiXResource):
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


class Subscription(ApiXResource):
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
