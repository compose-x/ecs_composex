#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re

from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS,
    PUBLIC_SUBNETS,
    STORAGE_SUBNETS,
    VPC_ID,
)

TAGS_KEY = "Tags"


def lookup_x_vpc_settings(lookup, session):
    """
    Method to set VPC settings from x-vpc

    :param boto3.session.Session session:
    :param dict lookup:
    :return: vpc_settings
    :rtype: dict
    """
    vpc_type = "ec2:vpc"
    subnet_type = "ec2:subnet"
    required_keys = [
        VPC_ID.title,
        PUBLIC_SUBNETS.title,
        APP_SUBNETS.title,
        STORAGE_SUBNETS.title,
    ]
    subnets_keys = [
        PUBLIC_SUBNETS.title,
        APP_SUBNETS.title,
        STORAGE_SUBNETS.title,
    ]
    if not all(key in lookup.keys() for key in required_keys):
        raise KeyError(
            "Missing keys for x-vpc Lookup. Got",
            lookup.keys(),
            "Expected",
            required_keys,
        )
    lookup_session = define_lookup_role_from_info(lookup, session)
    vpc_types = {
        vpc_type: {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:ec2:[a-z0-9-]+:[0-9]{12}:vpc/)(vpc-[a-z0-9]+)$"
        },
        subnet_type: {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:ec2:[a-z0-9-]+:[0-9]{12}:subnet/)(subnet-[a-z0-9]+)$"
        },
    }
    vpc_arn = find_aws_resource_arn_from_tags_api(
        lookup[VPC_ID.title],
        lookup_session,
        vpc_type,
        types=vpc_types,
        allow_multi=False,
    )
    vpc_re = re.compile(vpc_types[vpc_type]["regexp"])
    vpc_settings = {
        VPC_ID.title: vpc_re.match(vpc_arn).groups()[0],
        APP_SUBNETS.title: [],
        STORAGE_SUBNETS.title: [],
        PUBLIC_SUBNETS.title: [],
    }

    for subnet_key in subnets_keys:
        subnet_arns = find_aws_resource_arn_from_tags_api(
            lookup[subnet_key],
            lookup_session,
            subnet_type,
            types=vpc_types,
            allow_multi=True,
        )
        vpc_settings[subnet_key] = [
            re.match(vpc_types[subnet_type]["regexp"], subnet_arn).groups()[0]
            for subnet_arn in subnet_arns
        ]
    extra_subnets = [
        key
        for key in lookup.keys()
        if key not in required_keys and not key == "RoleArn"
    ]
    for subnet_name in extra_subnets:
        subnet_arns = find_aws_resource_arn_from_tags_api(
            lookup[subnet_name],
            lookup_session,
            subnet_type,
            types=vpc_types,
            allow_multi=True,
        )
        vpc_settings[subnet_name] = [
            re.match(vpc_types[subnet_type]["regexp"], subnet_arn).groups()[0]
            for subnet_arn in subnet_arns
        ]
    vpc_settings["session"] = lookup_session
    return vpc_settings
