#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to find the SQS streams in lookup
"""

import re

from botocore.exceptions import ClientError
from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.kinesis.kinesis_params import STREAM_ARN, STREAM_KMS_KEY_ID


def get_stream_config(logical_name, stream_arn, session):
    """

    :param str stream_arn:
    :param boto3.session.Session session:
    :return:
    """
    stream_parts = re.compile(
        r"(?:^arn:aws(?:-[a-z]+)?:kinesis:)([\S]+):([0-9]{12}):stream/([\S]+)$"
    )
    stream_name = stream_parts.match(stream_arn).groups()[2]
    client = session.client("kinesis")
    stream_config = {}
    try:
        stream_r = client.describe_stream(StreamName=stream_name)["StreamDescription"]
        stream_config.update(
            {
                logical_name: stream_r["StreamName"],
                STREAM_ARN.title: stream_r["StreamARN"],
            }
        )
        if keyisset("KeyId", stream_r):
            stream_config.update({STREAM_KMS_KEY_ID.title: stream_r["KeyId"]})
        return stream_config
    except client.exceptions.ResourceNotFoundException:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_stream_config(logical_name, lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    kinesis_types = {
        "kinesis": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:kinesis:[\S]+:[0-9]{12}:stream/)([\S]+)$"
        },
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    stream_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "kinesis",
        types=kinesis_types,
    )
    if not stream_arn:
        return None
    config = get_stream_config(logical_name, stream_arn, lookup_session)
    LOG.debug(config)
    return config
