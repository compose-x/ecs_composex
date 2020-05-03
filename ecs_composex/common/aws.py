# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
Common functions and variables fetched from AWS.
"""

import boto3


def get_region_azs(region=None, session=None, client=None):
    """Function to return the AZ from a given region. Uses default region for this

    :param region: override region_name for boto3.session.Session
    :type region: str
    :param session: override boto3.session.Session for the next client request
    :type session: boto3.session.Session()
    :param client: boto3 client
    :type client: boto3.client()

    :return: list of AZs in the given region
    :rtype: list
    """
    if client is None:
        if session is None:
            if region is None:
                session = boto3.session.Session()
            elif isinstance(region, str):
                session = boto3.session.Session(region_name=region)
        return session.client("ec2").describe_availability_zones()["AvailabilityZones"]
    return client.describe_availability_zones()["AvailabilityZones"]


def get_curated_azs(region=None, session=None, client=None):
    """Function to return curated list of AZs

    :param region: override region_name for boto3.session.Session
    :type region: str
    :param session: override boto3.session.Session for the next client request
    :type session: boto3.session.Session
    :param client: boto3 client to make the API call
    :type client: boto3.client

    :return: list of AZs from AWS
    :rtype: list
    """
    azs = get_region_azs(region, session, client)
    return [az["ZoneName"] for az in azs]


def get_account_id(session=None, client=None):
    """
    Function to get the current session account ID

    :param session: boto3 session to override API calls
    :type session: boto3.session.Session
    :param client: boto3 client to make API calls
    :type client: boto3.client

    :return: account ID
    :rtype: str
    """
    if client is not None:
        return client.get_caller_identity()["Account"]
    elif client is None and session is not None:
        return session.client("sts").get_caller_identity()["Account"]
    elif client is None and session is None:
        return boto3.client("sts").get_caller_identity()["Account"]
