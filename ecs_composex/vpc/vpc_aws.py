#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re

from boto3.session import Session
from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
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


def delete_subnet_from_settings(subnets, subnet_key, vpc_settings):
    """
    Deletes subnets that are not part of the VPC from vpc_settings

    :param list[dict] subnets:
    :param str subnet_key:
    :param dict vpc_settings:
    """
    for subnet_def in subnets:
        if subnet_def["VpcId"] != vpc_settings[VPC_ID.title]:
            for count, subnet_id in enumerate(vpc_settings[subnet_key]):
                if subnet_id == subnet_def["SubnetId"]:
                    LOG.error(
                        f"x-vpc.Lookup - {vpc_settings[subnet_key][count]}"
                        f" is not part of VPC {vpc_settings[VPC_ID.title]}"
                        "Removing it"
                    )
                    vpc_settings[subnet_key].pop(count)


def validate_subnets_belong_with_vpc(vpc_settings, subnet_keys, session=None):
    """
    Function to ensure all subnets belong to the identified VPC

    :param dict vpc_settings:
    :param list[str] subnet_keys:
    :param boto3.session.Session session:
    :raises: boto3.client.exceptions

    """
    if session is None:
        session = Session()
    client = session.client("ec2")
    for subnet_key in subnet_keys:
        subnets_r = client.describe_subnets(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [
                        vpc_settings[VPC_ID.title],
                    ],
                },
            ],
            SubnetIds=vpc_settings[subnet_key],
        )
        if keyisset("Subnets", subnets_r):
            delete_subnet_from_settings(subnets_r["Subnets"], subnet_key, vpc_settings)
        else:
            raise LookupError(
                f"None of the {subnet_key} subnets",
                ",".join(vpc_settings[subnet_key]),
                "are in VPC",
                vpc_settings[VPC_ID.title],
            )
    for key in vpc_settings.keys():
        if not keyisset(key, vpc_settings) and key in subnet_keys:
            raise KeyError(
                f"No subnets for {key} "
                f"have been identified in {vpc_settings[VPC_ID.title]}"
            )


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
    total_subnets_keys = subnets_keys + extra_subnets
    validate_subnets_belong_with_vpc(
        vpc_settings=vpc_settings,
        subnet_keys=total_subnets_keys,
        session=lookup_session,
    )
    return vpc_settings
