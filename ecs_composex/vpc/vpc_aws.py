#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

import re
from ecs_composex.common import keyisset, LOG
from ecs_composex.vpc.vpc_params import (
    VPC_ID,
    APP_SUBNETS,
    PUBLIC_SUBNETS,
    STORAGE_SUBNETS,
)

TAGS_KEY = "Tags"


def lookup_vpc_id(session, vpc_id):
    """

    :param session: boto3 session
    :param vpc_id: VPC ID
    :return:
    """
    args = {"VpcIds": [vpc_id]}
    arn_regexp = r"(^arn:(aws|aws-cn|aws-us-gov):ec2:([a-z]{2}-[\w]{2,6}-[0-9]{1}):([0-9]{12}):vpc\/(vpc-[a-z0-9]+)$)"
    arn_re = re.compile(arn_regexp)
    if vpc_id.startswith("arn:") and arn_re.match(vpc_id):
        LOG.debug(arn_re.findall(vpc_id))
        re_vpc_id = arn_re.findall(vpc_id)[-1][-1]
        re_vpc_owner = arn_re.findall(vpc_id)[-1][-2]
        args = {
            "VpcIds": [re_vpc_id],
            "Filters": [{"Name": "owner-id", "Values": [re_vpc_owner]}],
        }
        vpc_id = re_vpc_id
    elif vpc_id.startswith("arn:") and not arn_re.match(vpc_id):
        raise ValueError(
            "Vpc ARN is not valid. Got", vpc_id, "Valid ARN Regexp", arn_regexp
        )

    client = session.client("ec2")
    vpcs_r = client.describe_vpcs(**args)
    LOG.debug(vpcs_r)
    LOG.debug(vpcs_r["Vpcs"][0]["VpcId"])
    if keyisset("Vpcs", vpcs_r) and vpcs_r["Vpcs"][0]["VpcId"] == vpc_id:
        LOG.info(f"VPC Found and confirmed: {vpcs_r['Vpcs'][0]['VpcId']}")
        return vpcs_r["Vpcs"][0]["VpcId"]
    raise ValueError("No VPC found with ID", args["VpcIds"][0])


def define_filter_tags(tags):
    """
    Function to create the filters out of tags list

    :param list tags: list of Key/Value dict
    :return: filters
    :rtype: list
    """
    filters = []
    for tag in tags:
        key = list(tag.keys())[0]
        filter_name = f"tag:{key}"
        filter_values = [tag[key]]
        filters.append({"Name": filter_name, "Values": filter_values})
    return filters


def lookup_vpc_from_tags(session, tags):
    """
    Function to find a VPC from defined Tags

    :param boto3.session.Session session: boto3 session
    :param list tags: list of tags
    :return:
    """
    client = session.client("ec2")
    filters = define_filter_tags(tags)
    vpcs_r = client.describe_vpcs(Filters=filters)
    if keyisset("Vpcs", vpcs_r):
        if len(vpcs_r["Vpcs"]) > 1:
            raise ValueError(
                "There is more than one VPC with the provided tags.", filters
            )
        LOG.info(f"VPC found and confirmed: {vpcs_r['Vpcs'][0]['VpcId']}")
        return vpcs_r["Vpcs"][0]["VpcId"]
    raise ValueError("No VPC found with tags", filters)


def lookup_subnets_ids(session, ids, vpc_id):
    """
    Function to find subnets based on a list of subnet IDs

    :param session: boto3 session
    :param ids: list of subneet IDs
    :param str vpc_id: The VPC ID to use to search for the subnets
    :return: list of subnets
    :rtype: list
    """
    client = session.client("ec2")
    filters = [{"Name": "vpc-id", "Values": [vpc_id]}]
    subnets_r = client.describe_subnets(SubnetIds=ids, Filters=filters)
    if keyisset("Subnets", subnets_r):
        subnets = [subnet["SubnetId"] for subnet in subnets_r["Subnets"]]
        if not all(subnet["SubnetId"] in ids for subnet in subnets_r["Subnets"]):
            raise ValueError(
                "Subnets returned are invalid. Expected", ids, "got", subnets
            )
        print(subnets, ids)
        LOG.info(f"Subnets found and confirmed: {subnets}")
        return subnets
    raise ValueError("No Subnets found with provided IDs", ids)


def lookup_subnets_from_tags(session, tags, vpc_id, subnet_key=None):
    """
    Function to find a VPC from defined Tags

    :param boto3.session.Session session: boto3 session
    :param list tags: list of tags
    :param str vpc_id: The VPC ID to use to search for the subnets
    :param str subnet_key: For troubleshooting, allows to figure which subnets this was for.
    :return:
    """
    if subnet_key is None:
        subnet_key = "Subnets "
    client = session.client("ec2")
    filters = define_filter_tags(tags)
    filters.append({"Name": "vpc-id", "Values": [vpc_id]})
    subnets_r = client.describe_subnets(Filters=filters)
    if keyisset("Subnets", subnets_r):
        subnets = [subnet["SubnetId"] for subnet in subnets_r["Subnets"]]
        LOG.info(f"{subnet_key} found and confirmed: {subnets}")
        return subnets
    raise ValueError("No Subnets found with tags", filters)


def define_vpc_id(session, vpc_id_settings):
    """
    Method to confirm or find VPC ID

    :param boto3.session.Session session:
    :param vpc_id_settings:
    """
    if isinstance(vpc_id_settings, str):
        vpc_id = lookup_vpc_id(session, vpc_id_settings)
    elif (
        isinstance(vpc_id_settings, dict)
        and keyisset(TAGS_KEY, vpc_id_settings)
        and isinstance(vpc_id_settings[TAGS_KEY], list)
    ):
        vpc_id = lookup_vpc_from_tags(session, vpc_id_settings[TAGS_KEY])
    else:
        raise ValueError("VpcId is neither the VPC ID, the VPC Arn or a set of tags")
    return vpc_id


def define_subnet_ids(session, subnet_key, subnet_id_settings, vpc_settings):
    """
    Method to confirm or find VPC ID

    :param str subnet_key: Attribute name
    :param subnet_id_settings:
    :param dict vpc_settings: the VPC Settings to update
    """
    if isinstance(subnet_id_settings, str):
        vpc_settings[subnet_key] = lookup_subnets_ids(
            session, subnet_id_settings.split(","), vpc_settings[VPC_ID.title]
        )
    elif isinstance(subnet_id_settings, list):
        vpc_settings[subnet_key] = lookup_subnets_ids(
            session, subnet_id_settings, vpc_settings[VPC_ID.title]
        )
    elif (
        isinstance(subnet_id_settings, dict)
        and keyisset(TAGS_KEY, subnet_id_settings)
        and isinstance(subnet_id_settings[TAGS_KEY], list)
    ):
        vpc_settings[subnet_key] = lookup_subnets_from_tags(
            session,
            subnet_id_settings[TAGS_KEY],
            vpc_settings[VPC_ID.title],
            subnet_key,
        )
    else:
        raise ValueError(
            f"Subnets {subnet_key} is neither the CommaDelimitedList of IDs, a list of SubnetIDs, or tags"
        )


def lookup_x_vpc_settings(session, lookup_settings):
    """
    Method to set VPC settings from x-vpc

    :param boto3.session.Session session:
    :param dict lookup_settings:
    :return: vpc_settings
    :rtype: dict
    """

    required_keys = [
        VPC_ID.title,
        PUBLIC_SUBNETS.title,
        APP_SUBNETS.title,
        STORAGE_SUBNETS.title,
    ]
    subnets_keys = [PUBLIC_SUBNETS.title, APP_SUBNETS.title, STORAGE_SUBNETS.title]
    if not all(key in lookup_settings.keys() for key in required_keys):
        raise KeyError(
            "Missing keys for x-vpc Lookup. Got",
            lookup_settings.keys(),
            "Expected",
            required_keys,
        )
    vpc_settings = {
        VPC_ID.title: define_vpc_id(session, lookup_settings[VPC_ID.title]),
        APP_SUBNETS.title: [],
        STORAGE_SUBNETS.title: [],
        PUBLIC_SUBNETS.title: [],
    }

    for subnet_key in subnets_keys:
        define_subnet_ids(
            session, subnet_key, lookup_settings[subnet_key], vpc_settings
        )
    return vpc_settings
