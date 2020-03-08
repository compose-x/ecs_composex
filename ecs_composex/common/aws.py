# -*- coding: utf-8 -*-
"""Common variables fetched from AWS."""

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
    if session is None:
        if region is None:
            session = boto3.session.Session()
        elif isinstance(region, str):
            session = boto3.session.Session(region_name=region)
    if client is None:
        return session.client('ec2').describe_availability_zones()['AvailabilityZones']
    return client.describe_availability_zones()['AvailabilityZones']


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
    return [az['ZoneName'] for az in azs]


def get_account_id(session=None, client=None):
    """
    Function to get the current session account ID

    :param session: boto3 session to override API calls
    :type session: boto3.session.Session
    :param client: boto3 client to make API calls
    :type client: boto3.client

    :return: list of AZs
    :rtype: list
    """
    if client is not None:
        return client.get_caller_identity()['Account']
    elif client is None and session is not None:
        return session.client('sts').get_caller_identity()['Account']
    elif client is None and session is None:
        return boto3.client('sts').get_caller_identity()['Account']


CURATED_AZS = get_curated_azs()
ACCOUNT_ID = get_account_id()
BUCKET_NAME = f"cfn-templates-{ACCOUNT_ID[:6]}"
