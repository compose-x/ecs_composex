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
Module to define the DynamoDB tables mappings config from Lookup
"""

import re

from botocore.exceptions import ClientError

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    find_aws_resource_arn_from_tags_api,
    define_lookup_role_from_info,
)
from ecs_composex.dynamodb.dynamodb_params import TABLE_NAME, TABLE_ARN


def get_table_config(table_arn, session):
    """

    :param str table_arn:
    :param boto3.session.Session session:
    :return:
    """
    table_parts = re.compile(
        r"(?:^arn:aws(?:-[a-z]+)?:dynamodb:[\S]+:[0-9]+:table/)([\S]+)$"
    )
    table_name = table_parts.match(table_arn).groups()[0]
    table_config = {TABLE_NAME.title: table_name, TABLE_ARN.title: table_arn}
    client = session.client("dynamodb")
    try:
        table_r = client.describe_table(TableName=table_name)
        table_config.update(
            {
                TABLE_NAME.title: table_r["Table"]["TableName"],
                TABLE_ARN.title: table_r["Table"]["TableArn"],
            }
        )
        return table_config
    except client.exceptions.ResourceNotFoundException:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_dynamodb_config(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    dynamodb_types = {
        "dynamodb:table": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:dynamodb:[\S]+:[0-9]+:table\/)([\S]+)$"
        },
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    table_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "dynamodb:table",
        types=dynamodb_types,
    )
    if not table_arn:
        return None
    config = get_table_config(table_arn, lookup_session)
    LOG.debug(config)
    return config
