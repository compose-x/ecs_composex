# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to add topics and subscriptions to the SNS stack
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template
    from ecs_composex.sns.sns_stack import Topic

from troposphere.sns import Topic as CfnTopic

from ecs_composex.common.troposphere_tools import add_outputs
from ecs_composex.resources_import import import_record_properties
from ecs_composex.sns import metadata


def add_topics_to_template(template, topics):
    """Function to interate over the topics and add them to the CFN Template"""
    for topic in topics:
        topic_props = import_record_properties(topic.properties, CfnTopic)
        topic.cfn_resource = CfnTopic(
            topic.logical_name, Metadata=metadata, **topic_props
        )
        topic.init_outputs()
        topic.generate_outputs()
        template.add_resource(topic.cfn_resource)
        add_outputs(template, topic.outputs)


def import_sns_topics_to_template(
    new_topics: list[Topic],
    root_template: Template,
):
    """Entrypoint function to generate the SNS topics templates"""
    add_topics_to_template(root_template, new_topics)
    return root_template
