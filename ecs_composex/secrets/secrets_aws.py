#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to find the Secrets from AWS Tags
"""

from botocore.exceptions import ClientError
from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)


def get_secret_config(logical_name, secret_arn, session):
    """
    Function to get the secret config used to define its mapping

    :param str logical_name:
    :param str secret_arn:
    :param boto3.session.Session session:
    :return:
    """

    secret_config = {}
    client = session.client("secretsmanager")
    try:
        secret_r = client.describe_secret(SecretId=secret_arn)
        secret_config.update({logical_name: secret_r["ARN"], "Name": secret_r["Name"]})
        if keyisset("KmsKeyId", secret_r):
            secret_config.update({"KmsKeyId": secret_r["KmsKeyId"]})
        return secret_config
    except client.exceptions.ResourceNotFoundException:
        return None
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_secret_config(logical_name, lookup, session):
    """
    Function to find the DB in AWS account

    :param str logical_name: Logical name of the resource
    :param dict lookup: The Lookup definition
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    secrets_types = {
        "secretsmanager:secret": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:secretsmanager:[\w-]+:[0-9]{12}:secret:)([\S]+)(?:-[A-Za-z0-9]+)$"
        },
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    secret_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "secretsmanager:secret",
        types=secrets_types,
    )
    config = get_secret_config(logical_name, secret_arn, lookup_session)
    LOG.debug(config)
    return config
