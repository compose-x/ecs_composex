#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to find buckets and identify settings about these.
"""

import re

from botocore.exceptions import ClientError
from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)


def lookup_bucket_config(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    s3_types = {
        "s3": {"regexp": r"(?:^arn:aws(?:-[a-z]+)?:s3:::)([\S]+)$"},
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    bucket_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "s3",
        types=s3_types,
    )
    if not bucket_arn:
        return None
    config = return_bucket_config(bucket_arn, lookup_session)
    LOG.debug(config)
    return config
