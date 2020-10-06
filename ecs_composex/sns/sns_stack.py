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

from ecs_composex.common import keyisset, LOG
from ecs_composex.sns.sns_params import RES_KEY
from ecs_composex.sns.sns_templates import generate_sns_templates
from ecs_composex.sqs.sqs_params import RES_KEY as SQS_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import XResource


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

    keyword = "Topics"


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
                )

        template = create_sns_template(settings)
        super().__init__(title, stack_template=template, **kwargs)

    def handle_sqs(self, root_template, sqs_root_stack):
        """
        Function to handle the SQS configuration to allow SNS to send messages to queues.
        """

    def add_xdependencies(self, root_template, content):
        """
        Method to add a dependencies from other X-Resources
        :param troposphere.Template root_template: The ComposeX Root template
        :param dict content: the compose file content
        """
        resources = root_template.resources
        sqs_res = SQS_KEY.strip("x-") if SQS_KEY.startswith("x-") else SQS_KEY
        if SQS_KEY in content and sqs_res in resources:
            self.DependsOn.append(sqs_res)
            self.handle_sqs(root_template, resources[sqs_res])
