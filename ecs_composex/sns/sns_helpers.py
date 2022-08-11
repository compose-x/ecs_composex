#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.sns.sns_stack import Topic

from botocore.exceptions import ClientError
from compose_x_common.aws.sns import SNS_TOPIC_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere.sns import Topic as CfnTopic

from ecs_composex.common.logging import LOG
from ecs_composex.sns.sns_params import TOPIC_ARN, TOPIC_KMS_KEY, TOPIC_NAME


def create_sns_mappings(
    resources: list[Topic], settings: ComposeXSettings, module: XResourceModule
) -> None:
    """
    Creates the Mappings for x-sns
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in resources:
        resource.lookup_resource(
            SNS_TOPIC_ARN_RE, get_topic_config, CfnTopic.resource_type, "sns"
        )
        resource.generate_cfn_mappings_from_lookup_properties()
        resource.generate_outputs()
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )


def get_topic_config(topic: Topic, account_id: str, resource_id: str) -> dict | None:
    """
    Function to create the mapping definition for SNS topics
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
                    f"{topic.module.res_key}.{topic.name} - Topic uses the default AWS CMK."
                )
            else:
                LOG.warning(
                    f"{topic.module.res_key}.{topic.name} - KMS Key provided is not a valid ARN."
                )
            del attributes[TOPIC_KMS_KEY]
        topic_config.update(attributes)
        return topic_config
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise
