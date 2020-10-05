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

from os import path
from json import loads

from troposphere import Sub, ImportValue, Parameter
from troposphere.iam import Policy as IamPolicy

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.resource_settings import generate_export_strings


def get_access_types():
    with open(
        f"{path.abspath(path.dirname(__file__))}/s3_perms.json",
        "r",
        encoding="utf-8-sig",
    ) as perms_fd:
        return loads(perms_fd.read())


def generate_s3_bucket_resource_strings(res_name, attribute):
    """
    Function to generate the SSM and CFN import/export strings
    Returns the import in a tuple

    :param str res_name: name of the queue as defined in ComposeX File
    :param str|Parameter attribute: The attribute to use in Import Name.

    :returns: ImportValue for CFN
    :rtype: ImportValue
    """
    if isinstance(attribute, str):
        bucket_string = (
            f"${{{ROOT_STACK_NAME.title}}}{DELIM}{res_name}{DELIM}{attribute}"
        )
        objects_string = (
            f"${{{ROOT_STACK_NAME.title}}}{DELIM}{res_name}{DELIM}{attribute}/*"
        )
    elif isinstance(attribute, Parameter):
        bucket_string = (
            f"${{{ROOT_STACK_NAME.title}}}{DELIM}{res_name}{DELIM}{attribute.title}"
        )
        objects_string = (
            f"${{{ROOT_STACK_NAME.title}}}{DELIM}{res_name}{DELIM}{attribute.title}/*"
        )
    else:
        raise TypeError("Attribute can only be a string or Parameter")

    return [ImportValue(Sub(bucket_string)), ImportValue(Sub(objects_string))]


def generate_s3_permissions(resource_name, attribute, arn=None):
    """
    Function to generate IAM permissions for a given x-resource. Returns the mapping of these for the given resource.

    :param str resource_name: The name of the resource
    :param str attribute: the attribute of the resource we are using for Import
    :param str arn: The ARN of the resource if already looked up.
    :return: dict of the IAM policies associated with the resource.
    :rtype dict:
    """
    resource_policies = {}
    policies = get_access_types()
    for a_type in policies:
        clean_policy = {"Version": "2012-10-17", "Statement": []}
        LOG.debug(a_type)
        policy_doc = policies[a_type].copy()
        policy_doc["Sid"] = Sub(NONALPHANUM.sub("", f"{a_type}To{resource_name}"))
        policy_doc["Resource"] = (
            generate_export_strings(resource_name, attribute)
            if not arn
            else [f"{arn}/*", arn]
        )
        clean_policy["Statement"].append(policy_doc)
        resource_policies[a_type] = IamPolicy(
            PolicyName=Sub(
                NONALPHANUM.sub(
                    "", f"{a_type}{resource_name}${{{ROOT_STACK_NAME.title}}}"
                )
            ),
            PolicyDocument=clean_policy,
        )
    return resource_policies
