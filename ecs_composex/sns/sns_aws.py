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

"""
Module to find the SQS topics in lookup
"""

import re

from botocore.exceptions import ClientError

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.aws import (
    find_aws_resource_arn_from_tags_api,
    define_lookup_role_from_info,
)
from ecs_composex.sns.sns_params import TOPIC_ARN, TOPIC_KMS_KEY


def get_topic_config(logical_name, topic_arn, session):
    """
    Function to create the mapping definition for SNS topics

    :param str logical_name: The logical name of the resource
    :param str topic_arn:
    :param boto3.session.Session session:
    :return:
    """
    topic_parts = re.compile(r"(?:^arn:aws(?:-[a-z]+)?:sns:[\S]+:[0-9]+:)([\S]+)$")
    topic_name = topic_parts.match(topic_arn).groups()[0]
    topic_config = {logical_name: topic_name, TOPIC_ARN.title: topic_arn}
    client = session.client("sns")
    try:
        topic_r = client.get_topic_attributes(TopicArn=topic_arn)
        topic_config.update({logical_name: topic_r["Attributes"]["TopicArn"]})
        if keyisset("Attributes", topic_r) and keyisset(
            "KmsMasterKeyId", topic_r["Attributes"]
        ):
            kms_key_id = topic_r["Attributes"]["KmsMasterKeyId"]
            if kms_key_id.startswith("arn:aws"):
                topic_config.update({TOPIC_KMS_KEY.title: kms_key_id})
            else:
                LOG.warning(
                    "The KMS Key provided is not an ARN. Implementation requires full ARN today"
                )
        else:
            LOG.info(f"No KMS Key associated with topic {topic_name}")
        return topic_config
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_topic_config(logical_name, lookup, session):
    """
    Function to find the DB in AWS account

    :param str logical_name: The logical name of the resource
    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    sns_types = {
        "sns": {"regexp": r"(?:^arn:aws(?:-[a-z]+)?:sns:[\S]+:[0-9]+:)([\S]+)$"},
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    topic_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "sns",
        types=sns_types,
    )
    if not topic_arn:
        return None
    config = get_topic_config(logical_name, topic_arn, lookup_session)
    LOG.debug(config)
    return config
