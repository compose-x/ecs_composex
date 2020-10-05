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
Module to apply SNS settings onto ECS Services
"""

from troposphere.sns import Topic

from ecs_composex.common import keyisset
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resource_permissions import apply_iam_based_resources
from ecs_composex.resource_settings import (
    generate_resource_permissions,
)
from ecs_composex.sns.sns_params import TOPIC_ARN_T
from ecs_composex.sns.sns_perms import ACCESS_TYPES
from ecs_composex.sns.sns_stack import Topic as XTopic


def handle_new_topics(
    xresources,
    services_families,
    services_stack,
    res_root_stack,
    l_topics,
    nested=False,
):
    topics_r = []
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if isinstance(s_resources[resource_name], Topic):
            topics_r.append(s_resources[resource_name].title)
        elif issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_topics(
                xresources,
                services_families,
                services_stack,
                s_resources[resource_name],
                l_topics,
                nested=True,
            )
    for topic_name in xresources:
        if topic_name in topics_r:
            topic = xresources[topic_name]
            topic.generate_resource_envvars(TOPIC_ARN_T)
            perms = generate_resource_permissions(topic_name, ACCESS_TYPES, TOPIC_ARN_T)
            apply_iam_based_resources(
                topic,
                services_families,
                services_stack,
                res_root_stack,
                perms,
                nested,
            )
            del l_topics[topic_name]


def sns_to_ecs(
    topics, services_stack, services_families, res_root_stack, settings, **kwargs
):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    l_topics = topics[XTopic.keyword].copy()
    if keyisset(XTopic.keyword, topics):
        handle_new_topics(
            topics[XTopic.keyword],
            services_families,
            services_stack,
            res_root_stack,
            l_topics,
        )
