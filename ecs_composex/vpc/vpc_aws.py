# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from boto3.session import Session
from compose_x_common.aws.arns import ARNS_PER_TAGGINGAPI_TYPE
from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api
from ecs_composex.common.logging import LOG
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
    filters = [
        {
            "Name": "vpc-id",
            "Values": [
                vpc_settings[VPC_ID.title],
            ],
        },
    ]
    for subnet_key in subnet_keys:
        subnets_r = client.describe_subnets(
            Filters=filters,
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


def lookup_x_vpc_settings(vpc_resource):
    """
    Method to set VPC settings from x-vpc

    :param ecs_composex.vpc.vpc_stack.Vpc vpc_resource:
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
    vpc_arn = find_aws_resource_arn_from_tags_api(
        vpc_resource.lookup[VPC_ID.title],
        vpc_resource.lookup_session,
        vpc_type,
        allow_multi=False,
    )
    vpc_re = ARNS_PER_TAGGINGAPI_TYPE[vpc_type]
    vpc_settings = {
        VPC_ID.title: vpc_re.match(vpc_arn).group("id"),
        APP_SUBNETS.title: [],
        STORAGE_SUBNETS.title: [],
        PUBLIC_SUBNETS.title: [],
    }

    for subnet_key in subnets_keys:
        subnet_arns = find_aws_resource_arn_from_tags_api(
            vpc_resource.lookup[subnet_key],
            vpc_resource.lookup_session,
            subnet_type,
            allow_multi=True,
        )
        if not isinstance(subnet_arns, list):
            subnet_arns = [subnet_arns]
        vpc_settings[subnet_key] = [
            ARNS_PER_TAGGINGAPI_TYPE[subnet_type].match(subnet_arn).group("id")
            for subnet_arn in subnet_arns
            if ARNS_PER_TAGGINGAPI_TYPE[subnet_type].match(subnet_arn)
        ]
    extra_subnets = [
        key
        for key in vpc_resource.lookup.keys()
        if key not in required_keys and not key == "RoleArn"
    ]
    for subnet_name in extra_subnets:
        subnet_arns = find_aws_resource_arn_from_tags_api(
            vpc_resource.lookup[subnet_name],
            vpc_resource.lookup_session,
            subnet_type,
            allow_multi=True,
        )
        if not isinstance(subnet_arns, list):
            subnet_arns = [subnet_arns]
        vpc_settings[subnet_name] = [
            ARNS_PER_TAGGINGAPI_TYPE[subnet_type].match(subnet_arn).group("id")
            for subnet_arn in subnet_arns
            if ARNS_PER_TAGGINGAPI_TYPE[subnet_type].match(subnet_arn)
        ]
    vpc_settings["session"] = vpc_resource.lookup_session
    total_subnets_keys = subnets_keys + extra_subnets
    validate_subnets_belong_with_vpc(
        vpc_settings=vpc_settings,
        subnet_keys=total_subnets_keys,
        session=vpc_resource.lookup_session,
    )
    return vpc_settings
