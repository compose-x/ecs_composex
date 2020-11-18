﻿#  -*- coding: utf-8 -*-
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
Module to find the SQS queues in lookup
"""

import re

from botocore.exceptions import ClientError

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.aws import (
    find_aws_resource_arn_from_tags_api,
    define_lookup_role_from_info,
)
from ecs_composex.sqs.sqs_params import SQS_ARN, SQS_KMS_KEY_T


def get_queue_config(logical_name, queue_arn, session):
    """

    :param str queue_arn:
    :param boto3.session.Session session:
    :return:
    """
    queue_parts = re.compile(r"(?:^arn:aws(?:-[a-z]+)?:sqs:)([\S]+):([0-9]+):([\S]+)$")
    queue_name = queue_parts.match(queue_arn).groups()[2]
    queue_owner = queue_parts.match(queue_arn).groups()[1]
    queue_config = {logical_name: queue_name, SQS_ARN.title: queue_arn}
    client = session.client("sqs")
    try:
        url_r = client.get_queue_url(
            QueueName=queue_name, QueueOwnerAWSAccountId=queue_owner
        )
        queue_config.update({logical_name: url_r["QueueUrl"]})
        try:
            encryption_config_r = client.get_queue_attributes(
                QueueUrl=url_r["QueueUrl"], AttributeNames=["KmsMasterKeyId"]
            )
            if keyisset("Attributes", encryption_config_r) and keyisset(
                "KmsMasterKeyId", encryption_config_r["Attributes"]
            ):
                kms_key_id = encryption_config_r["Attributes"]["KmsMasterKeyId"]
                if kms_key_id.startswith("arn:aws"):
                    queue_config.update(
                        {
                            SQS_KMS_KEY_T: encryption_config_r["Attributes"][
                                "KmsMasterKeyId"
                            ]
                        }
                    )
                else:
                    LOG.warning(
                        "The KMS Key provided is not an ARN. Implementation requires full ARN today"
                    )
            else:
                LOG.info(f"No KMS Key associated with {queue_name}")
        except client.exceptions.InvalidAttributeName as error:
            LOG.error("Failed to retrieve the Queue attributes")
            LOG.error(error)
        return queue_config
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_queue_config(logical_name, lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    sqs_types = {
        "sqs": {"regexp": r"(?:^arn:aws(?:-[a-z]+)?:sqs:[\S]+:[0-9]+:)([\S]+)$"},
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    queue_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "sqs",
        types=sqs_types,
    )
    if not queue_arn:
        return None
    config = get_queue_config(logical_name, queue_arn, lookup_session)
    LOG.debug(config)
    return config
