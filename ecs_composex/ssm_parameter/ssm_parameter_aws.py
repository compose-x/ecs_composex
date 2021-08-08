#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to find the SQS queues in lookup
"""

import re

from botocore.exceptions import ClientError

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.ssm_parameter.ssm_params import SSM_PARAM_ARN, SSM_PARAM_NAME


def lookup_param_config(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    ssm_re = re.compile(r"(?:^arn:aws(?:-[a-z]+)?:ssm:[\S]+:[0-9]+:parameter)(/[\S]+)$")
    ssm_types = {
        "ssm": {"regexp": ssm_re.pattern},
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    param_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "ssm",
        types=ssm_types,
    )
    if not param_arn:
        return None
    config = {
        SSM_PARAM_NAME.title: ssm_re.match(param_arn).groups()[-1],
        SSM_PARAM_ARN.title: param_arn,
    }
    LOG.debug(config)
    return config
