#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

from troposphere import GetAtt, Ref

from ecs_composex.common import keyisset, LOG
from ecs_composex.common.compose_resources import XResource
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.sns.sns_params import RES_KEY, TOPIC_NAME, TOPIC_ARN, TOPIC_KMS_KEY
from ecs_composex.sns.sns_perms import ACCESS_TYPES
from ecs_composex.sns.sns_templates import generate_sns_templates
from ecs_composex.sqs.sqs_params import RES_KEY as SQS_KEY


def create_sns_template(settings):
    """
    Function to create SNS templates as part of ECS ComposeX.

    :param settings:
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return: SNS root template
    :rtype: troposphere.Template
    """
    if keyisset(RES_KEY, settings.compose_content):
        LOG.debug(f"Processing {RES_KEY} package")
        return generate_sns_templates(settings)


class Topic(XResource):
    """
    Class for SNS Topics
    """

    policies_scaffolds = ACCESS_TYPES
    keyword = "Topics"

    def __init__(self, name, definition, settings):
        super().__init__(name, definition, settings)
        self.arn_attr = TOPIC_ARN
        self.main_attr = TOPIC_NAME
        self.kms_attr = TOPIC_KMS_KEY
        self.arn_attr_value = self.arn_attr
        self.main_attr_value = self.main_attr
        self.kms_attr_value = self.kms_attr

    def init_outputs(self):
        self.output_properties = {
            TOPIC_ARN.title: (self.logical_name, self.cfn_resource, Ref, None),
            TOPIC_NAME.title: (
                f"{self.logical_name}{TOPIC_NAME.title}",
                self.cfn_resource,
                GetAtt,
                TOPIC_NAME.title,
            ),
            self.arn_attr.title: (self.logical_name, self.cfn_resource, Ref, None),
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
        if keyisset(Topic.keyword, settings.compose_content[RES_KEY]):
            for resource_name in settings.compose_content[RES_KEY][Topic.keyword]:
                settings.compose_content[RES_KEY][Topic.keyword][resource_name] = Topic(
                    resource_name,
                    settings.compose_content[RES_KEY][Topic.keyword][resource_name],
                    settings,
                )

        if keyisset(Subscription.keyword, settings.compose_content[RES_KEY]):
            for resource_name in settings.compose_content[RES_KEY][
                Subscription.keyword
            ]:
                settings.compose_content[RES_KEY][Subscription.keyword][
                    resource_name
                ] = Topic(
                    resource_name,
                    settings.compose_content[RES_KEY][Subscription.keyword][
                        resource_name
                    ],
                    settings,
                )

        template = create_sns_template(settings)
        super().__init__(title, stack_template=template, **kwargs)

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
