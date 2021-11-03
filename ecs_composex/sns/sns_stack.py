#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref

from ecs_composex.common import build_template
from ecs_composex.common.compose_resources import XResource
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.sns.sns_aws import lookup_topic_config
from ecs_composex.sns.sns_params import MOD_KEY, RES_KEY, TOPIC_ARN, TOPIC_NAME
from ecs_composex.sns.sns_templates import generate_sns_templates
from ecs_composex.sqs.sqs_params import RES_KEY as SQS_KEY


def create_sns_mappings(resources, settings):
    if not keyisset(RES_KEY, settings.mappings):
        mappings = {}
        settings.mappings[RES_KEY] = mappings
    else:
        mappings = settings.mappings[RES_KEY]
    for resource in resources:
        resource_config = lookup_topic_config(
            resource.logical_name, resource.lookup, settings.session
        )
        if resource_config:
            mappings.update({resource.logical_name: resource_config})


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
