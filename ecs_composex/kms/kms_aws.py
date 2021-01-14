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
Module to find the SQS keys in lookup
"""

from botocore.exceptions import ClientError

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    find_aws_resource_arn_from_tags_api,
    define_lookup_role_from_info,
)
from ecs_composex.kms.kms_params import (
    KMS_KEY_ARN,
    KMS_KEY_ID,
    KMS_KEY_ALIAS_NAME,
    KMS_KEY_ALIAS_ARN,
)


def get_key_config(logical_name, key_arn, session):
    """

    :param str key_arn:
    :param boto3.session.Session session:
    :return:
    """
    key_config = {KMS_KEY_ARN.title: key_arn}
    client = session.client("kms")
    try:
        key_desc = client.describe_key(KeyId=key_arn)
        key_config.update(
            {
                KMS_KEY_ARN.title: key_desc["KeyMetadata"]["Arn"],
                logical_name: key_desc["KeyMetadata"]["KeyId"],
            }
        )
        try:
            aliases_r = client.list_aliases(KeyId=key_desc["KeyMetadata"]["KeyId"])
            key_config.update(
                {
                    KMS_KEY_ALIAS_NAME.title: aliases_r["Aliases"][0]["AliasName"],
                    KMS_KEY_ALIAS_ARN.title: aliases_r["Aliases"][0]["AliasArn"],
                }
            )
        except client.exceptions.NotFoundException:
            LOG.debug(f"No alias was found for KMS Key {key_config[KMS_KEY_ID.title]}")
        return key_config
    except client.exceptions.QueueDoesNotExist:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_key_config(logical_name, lookup, session):
    """
    Function to find the DB in AWS account

    :param str logical_name:
    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    kms_types = {
        "kms:key": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:kms:[\S]+:[0-9]+:)((key/)([\S]+))$"
        },
        "kms:alias": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:kms:[\S]+:[0-9]+:)((alias/)([\S]+))$"
        },
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    key_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "kms:key",
        types=kms_types,
    )
    if not key_arn:
        return None
    config = get_key_config(logical_name, key_arn, lookup_session)
    LOG.debug(config)
    return config
