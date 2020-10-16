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


def define_tagsgroups_filter_tags(tags):
    """
    Function to create the filters out of tags list

    :param list tags: list of Key/Value dict
    :return: filters
    :rtype: list
    """
    filters = []
    for tag in tags:
        key = list(tag.keys())[0]
        filter_name = key
        filter_value = tag[key]
        filters.append({"Key": filter_name, "Values": (filter_value,)})
    return filters


def get_resources_from_tags(session, aws_resource_search, search_tags):
    """

    :param boto3.session.Session session: The boto3 session for API calls
    :param str aws_resource_search: AWS Service short code, ie. rds, ec2
    :param str res_type: Resource type we are after within the AWS Service, ie. cluster, instance
    :param list search_tags: The tags to search the resource with.
    :return:
    """
    LOG.info(aws_resource_search)
    try:
        client = session.client("resourcegroupstaggingapi")
        resources_r = client.get_resources(
            ResourceTypeFilters=[aws_resource_search], TagFilters=search_tags
        )
        return resources_r
    except ClientError as error:
        LOG.error(error)
        LOG.error("Not processing this resource. Skipping")
        return None


def handle_multi_results(arns, name, res_type, regexp):
    """
    Function to evaluate more than one result to see if we can match an unique name.

    :param list arns:
    :param str name:
    :param str res_type:
    :param str regexp:
    :raises LookupError:
    :return: The ARN of the resource matching the name.
    """
    found = 0
    found_arn = None
    re_finder = re.compile(regexp)
    for arn in arns:
        found_name = re_finder.match(arn).groups()[0]
        if found_name and found_name == name:
            found += 1
            found_arn = arn
    if found == 1:
        LOG.info(f"Matched {res_type} {name}")
        return found_arn
    elif found > 1:
        raise LookupError(
            f"More than one result was found for {name} / {res_type} "
            "but could not match the name to a single resource."
            "Found",
            arns,
        )
    elif found == 0:
        raise LookupError(
            f"No {res_type} named {name} was found with the provided tags."
            " Found with provided tags",
            [re_finder.match(arn).groups()[0] for arn in arns],
        )


def handle_search_results(arns, name, res_types, aws_resource_search):
    """
    Function to parse tag resource search results

    :param list arns:
    :param str name:
    :param dict res_types:
    :param str aws_resource_search:
    :return:
    """
    if not arns:
        raise LookupError(
            "No resources were found with the provided tags and information"
        )
    if arns and isinstance(name, str):
        return handle_multi_results(
            arns, name, aws_resource_search, res_types[aws_resource_search]["regexp"]
        )
    elif not name and len(arns) == 1:
        LOG.info(f"Matched {aws_resource_search} to AWS Resource")
        return arns[0]
    elif not name and len(arns) != 1:
        raise LookupError(
            f"More than one resource {name}:{aws_resource_search} was found with the current tags."
            "Found",
            arns,
        )


def validate_search_input(res_types, res_type):
    """
    Function to validate the search query

    :param info:
    :param res_types:
    :param res_type:
    :return:
    """

    if not isinstance(res_type, str):
        raise KeyError("type must be one of", res_types.keys(), "Got", res_type)
    if res_type not in res_types.keys():
        raise KeyError(
            f"There is not resource type {res_type} defined. Got", res_types.keys()
        )


def find_aws_resource_arn_from_tags_api(info, session, aws_resource_search, types=None):
    """
    Function to find the RDS DB based on info

    :param dict info:
    :param boto3.session.Session session: Boto3 session for clients
    :param str aws_resource_search: Resource type we are after within the AWS Service, ie. cluster, instance
    :param dict types: Additional types to match.
    :return:
    """
    res_types = {
        "secretsmanager:secret": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:secretsmanager:[\w-]+:[0-9]{12}:secret:)([\S]+)(?:-[A-Za-z0-9]+)$"
        },
    }
    if types is not None and isinstance(types, dict):
        res_types.update(types)
    validate_search_input(res_types, aws_resource_search)
    search_tags = (
        define_tagsgroups_filter_tags(info["Tags"]) if keyisset("Tags", info) else ()
    )
    name = info["Name"] if keyisset("Name", info) else None

    resources_r = get_resources_from_tags(session, aws_resource_search, search_tags)
    arns = [i["ResourceARN"] for i in resources_r["ResourceTagMappingList"]]
    return handle_search_results(arns, name, res_types, aws_resource_search)


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
