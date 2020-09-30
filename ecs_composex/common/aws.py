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
from botocore.exceptions import ClientError

from ecs_composex.common import LOG


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


def assert_can_create_stack(client, name):
    """
    Checks whether a stack already exists or not
    """
    try:
        client.describe_stacks(StackName=name)
        return False
    except ClientError as error:
        if (
            error.response["Error"]["Code"] == "ValidationError"
            and error.response["Error"]["Message"].find("does not exist") > 0
        ):
            return True
        raise error


def assert_can_update_stack(client, name):
    """
    Checks whether a stack already exists or not
    """
    can_update_statuses = [
        "CREATE_COMPLETE",
        "ROLLBACK_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    ]
    res = client.describe_stacks(StackName=name)
    if not res["Stacks"]:
        return False
    stack = res["Stacks"][0]
    LOG.info(stack["StackStatus"])
    if stack["StackStatus"] in can_update_statuses:
        return True
    return False


def deploy(settings, root_stack):
    """
    Function to deploy (create or update) the stack to CFN.
    :param ComposeXSettings settings:
    :param ComposeXStack root_stack:
    :return:
    """
    if not settings.upload:
        raise RuntimeError(
            "You selected --no-upload, which is incompatible with --deploy."
        )
    elif not root_stack.TemplateURL.startswith("https://"):
        raise ValueError(
            f"The URL for the stack is incorrect.: {root_stack.TemplateURL}",
            "TemplateURL must be a s3 URL",
        )
    client = settings.session.client("cloudformation")
    if assert_can_create_stack(client, settings.name):
        res = client.create_stack(
            StackName=settings.name,
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            Parameters=root_stack.render_parameters_list_cfn(),
            TemplateURL=root_stack.TemplateURL,
        )
        LOG.info(f"Stack {settings.name} successfully deployed.")
        LOG.info(res["StackId"])
        return res["StackId"]
    elif assert_can_update_stack(client, settings.name):
        LOG.warning(f"Stack {settings.name} already exists. Updating.")
        res = client.update_stack(
            StackName=settings.name,
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            Parameters=root_stack.render_parameters_list_cfn(),
            TemplateURL=root_stack.TemplateURL,
        )
        LOG.info(f"Stack {settings.name} successfully updating.")
        LOG.info(res["StackId"])
        return res["StackId"]
    return None
