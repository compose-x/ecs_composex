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


def get_region_azs(session):
    """Function to return the AZ from a given region. Uses default region for this

    :param boto3.session.Session session: Boto3 session

    :return: list of AZs in the given region
    :rtype: list
    """
    return session.client("ec2").describe_availability_zones()["AvailabilityZones"]


def get_account_id(session):
    """
    Function to get the current session account ID

    :param boto3.session.Session session: Boto3 Session to make the API call.

    :return: account ID
    :rtype: str
    """
    return session.client("sts").get_caller_identity()["Account"]


def get_curated_azs(session):
    """Function to return curated list of AZs

    :param boto3.session.Session session: Boto3 Session to make the API call.

    :return: list of AZs from AWS
    :rtype: list
    """
    azs = get_region_azs(session)
    return [az["ZoneName"] for az in azs]
