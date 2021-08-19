#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Common functions and variables fetched from AWS.
"""
import re
import secrets
from string import ascii_lowercase
from time import sleep

from botocore.exceptions import ClientError
from compose_x_common.aws import get_assume_role_session, validate_iam_role_arn
from compose_x_common.compose_x_common import keyisset
from tabulate import tabulate

from ecs_composex.common import LOG
from ecs_composex.iam import ROLE_ARN_ARG


def get_cross_role_session(session, arn, region_name=None, session_name=None):
    """
    Function to override ComposeXSettings session to specific session for Lookup

    :param boto3.session.Session session: The original session fetching the credentials for X-Role
    :param str arn:
    :param str region_name: Name of region for session
    :param str session_name: Override name of the session
    :return: boto3 session from lookup settings
    :rtype: boto3.session.Session
    """
    if not session_name:
        session_name = "ComposeX@Lookup"
    try:
        return get_assume_role_session(
            session, arn, region=region_name, session_name=session_name
        )
    except ClientError:
        LOG.error(f"Failed to use the Role ARN {arn}")
        raise


def define_lookup_role_from_info(info, session):
    """
    Function to override ComposeXSettings session to specific session for Lookup

    :param info:
    :param session:
    :return: boto3 session from lookup settings
    :rtype: boto3.session.Session
    """
    if not keyisset(ROLE_ARN_ARG, info):
        return session
    validate_iam_role_arn(info[ROLE_ARN_ARG])
    return get_cross_role_session(session, info[ROLE_ARN_ARG])


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
    :param list search_tags: The tags to search the resource with.
    :return:
    """
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


def handle_multi_results(arns, name, res_type, regexp, allow_multi=False):
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
    elif not allow_multi and found > 1:
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
    elif allow_multi and found > 1:
        LOG.info(f"Found multiple resources for {res_type} and Name/Id {name}.")
        return arns


def handle_search_results(
    arns, name, res_types, aws_resource_search, allow_multi=False
):
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
            "No resources were found with the provided tags and information",
            name,
            aws_resource_search,
        )
    if arns and isinstance(name, str):
        return handle_multi_results(
            arns,
            name,
            aws_resource_search,
            res_types[aws_resource_search]["regexp"],
            allow_multi=allow_multi,
        )
    elif not name and len(arns) == 1:
        LOG.info(f"Matched {aws_resource_search} to AWS Resource")
        return arns[0]
    elif not allow_multi and not name and len(arns) > 1:
        raise LookupError(
            f"More than one resource {name}:{aws_resource_search} was found with the current tags."
            "Found",
            arns,
        )
    elif allow_multi and len(arns) > 1:
        return arns


def validate_search_input(res_types, res_type):
    """
    Function to validate the search query

    :param dict res_types:
    :param str res_type:
    :return:
    """

    if not isinstance(res_type, str):
        raise KeyError("type must be one of", res_types.keys(), "Got", res_type)
    if res_type not in res_types.keys():
        raise KeyError(
            f"There is not resource type {res_type} defined. Got",
            res_types.keys(),
        )


def find_aws_resource_arn_from_tags_api(
    info, session, aws_resource_search, types=None, allow_multi=False
):
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
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:secretsmanager:[\w-]+:[0-9]{12}:secret:)([\S]+)(?:-[A-Za-z0-9]{1,6})$"
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
    LOG.debug(search_tags)
    if not resources_r or not keyisset("ResourceTagMappingList", resources_r):
        arns = []
    else:
        arns = [i["ResourceARN"] for i in resources_r["ResourceTagMappingList"]]
    return handle_search_results(
        arns, name, res_types, aws_resource_search, allow_multi=allow_multi
    )


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
        stack_r = client.describe_stacks(StackName=name)
        if not keyisset("Stacks", stack_r):
            return True
        stacks = stack_r["Stacks"]
        if len(stacks) != 1:
            raise LookupError("Too many stacks found with machine name", name)
        stack = stacks[0]
        if stack["StackStatus"] == "REVIEW_IN_PROGRESS":
            return stack
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


def validate_stack_availability(settings, root_stack):
    """
    Function to check that the stack can be updated
    :param settings:
    :param root_stack:
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


def deploy(settings, root_stack):
    """
    Function to deploy (create or update) the stack to CFN.
    :param ComposeXSettings settings:
    :param ComposeXStack root_stack:
    :return:
    """
    validate_stack_availability(settings, root_stack)
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


def get_change_set_status(client, change_set_name, settings):
    pending_statuses = [
        "CREATE_PENDING",
        "CREATE_IN_PROGRESS",
        "DELETE_PENDING",
        "DELETE_IN_PROGRESS",
        "REVIEW_IN_PROGRESS",
    ]
    success_statuses = ["CREATE_COMPLETE", "DELETE_COMPLETE"]
    failed_statuses = ["DELETE_FAILED", "FAILED"]
    ready = False
    status = None
    while not ready:
        status = client.describe_change_set(
            ChangeSetName=change_set_name, StackName=settings.name
        )
        if status["Status"] in failed_statuses:
            raise SystemExit("Change set is unsucessful", status["Status"])
        if status["Status"] in pending_statuses:
            print(
                "ChangeSet creation in progress. Waiting 10 seconds",
                end="\r",
                flush=True,
            )
            sleep(10)
        elif status["Status"] in success_statuses:
            ready = True

    print(
        tabulate(
            [
                [
                    change["ResourceChange"]["LogicalResourceId"],
                    change["ResourceChange"]["ResourceType"],
                    change["ResourceChange"]["Action"],
                ]
                for change in status["Changes"]
            ],
            ["LogicalResourceId", "ResourceType", "Action"],
            tablefmt="rst",
        )
    )
    return status


def plan(settings, root_stack):
    """
    Function to create a recursive change-set and return diffs
    :param ComposeXSettings settings:
    :param ComposeXStack root_stack:
    :return:
    """
    validate_stack_availability(settings, root_stack)
    client = settings.session.client("cloudformation")
    change_set_name = f"{settings.name}" + "".join(
        secrets.choice(ascii_lowercase) for _ in range(10)
    )
    if assert_can_create_stack(client, settings.name) or assert_can_update_stack(
        client, settings.name
    ):
        client.create_change_set(
            StackName=settings.name,
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            Parameters=root_stack.render_parameters_list_cfn(),
            TemplateURL=root_stack.TemplateURL,
            UsePreviousTemplate=False,
            IncludeNestedStacks=True,
            ChangeSetType="CREATE",
            ChangeSetName=change_set_name,
        )
        status = get_change_set_status(client, change_set_name, settings)
        if status:
            apply_q = input("Want to apply? [yN]: ")
            if apply_q in ["y", "Y", "YES", "Yes", "yes"]:
                client.execute_change_set(
                    ChangeSetName=change_set_name, StackName=settings.name
                )
            else:
                delete_q = input("Cleanup ChangeSet ? [yN]: ")
                if delete_q in ["y", "Y", "YES", "Yes", "yes"]:
                    client.delete_stack(StackName=settings.name)
