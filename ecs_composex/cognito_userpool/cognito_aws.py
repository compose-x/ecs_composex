#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to find the Cognito UserPools from tagging API
"""

import re

from compose_x_common.compose_x_common import keyisset

from ecs_composex.cognito_userpool.cognito_params import (
    USERPOOL_ARN,
    USERPOOL_DOMAIN,
    USERPOOL_ID,
)
from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)


def get_userpool_config(userpool_arn, session):
    """

    :param str userpool_arn:
    :param boto3.session.Session session:
    :return:
    """
    userpool_parts = re.compile(
        r"(?:^arn:aws(?:-[a-z]+)?:cognito-idp:[\S]+:[0-9]{12}:userpool/)([\S]+)$"
    )
    userpool_id = userpool_parts.match(userpool_arn).groups()[0]
    userpool_config = {
        USERPOOL_ARN.title: userpool_arn,
        USERPOOL_ID.title: userpool_id,
    }
    client = session.client("cognito-idp")
    try:
        userpool_r = client.describe_user_pool(UserPoolId=userpool_id)
        if keyisset("CustomDomain", userpool_r["UserPool"]):
            userpool_config[USERPOOL_DOMAIN.title] = userpool_r["UserPool"][
                "CustomDomain"
            ]
        elif keyisset("Domain", userpool_r["UserPool"]):
            userpool_config[USERPOOL_DOMAIN.title] = userpool_r["UserPool"]["Domain"]
        LOG.debug(f"Pool domain is {userpool_config[USERPOOL_DOMAIN.title]}")
    except client.exceptions:
        LOG.error("Failed to retrieve the Pool Domain. Moving on.")
    return userpool_config


def lookup_userpool_config(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    lookup_types = {
        "cognito-idp": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:cognito-idp:[\S]+:[0-9]{12}:userpool/)([\S]+)$"
        },
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    userpool_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "cognito-idp",
        types=lookup_types,
    )
    if not userpool_arn:
        return None
    config = get_userpool_config(userpool_arn, lookup_session)
    LOG.debug(config)
    return config
