#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to find the CodeGuru profiles from tagging API
"""

import re

from ecs_composex.codeguru_profiler.codeguru_profiler_params import (
    PROFILER_ARN,
    PROFILER_NAME,
)
from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)


def get_profile_config(profile_arn, session):
    """

    :param str profile_arn:
    :param boto3.session.Session session:
    :return:
    """
    profile_parts = re.compile(
        r"(?:^arn:aws(?:-[a-z]+)?:codeguru-profiler:[\S]+:[0-9]{12}:profilingGroup/)([\S]+)$"
    )
    profile_name = profile_parts.match(profile_arn).groups()[0]
    profile_config = {
        PROFILER_ARN.title: profile_arn,
        PROFILER_NAME.title: profile_name,
    }
    return profile_config


def lookup_profile_config(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    codeguru_profiler_re = re.compile(
        r"(?:^arn:aws(?:-[a-z]+)?:codeguru-profiler:[\S]+:[0-9]{12}:profilingGroup/)([\S]+)$"
    )
    lookup_types = {
        "codeguru-profiler": {"regexp": codeguru_profiler_re.pattern},
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    profile_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "codeguru-profiler",
        types=lookup_types,
    )
    if not profile_arn:
        return None
    config = get_profile_config(profile_arn, lookup_session)
    LOG.debug(config)
    return config
