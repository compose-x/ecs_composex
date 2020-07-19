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
import re
from botocore.exceptions import ClientError
from ecs_composex.common import LOG, keyisset


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
