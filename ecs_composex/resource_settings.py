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

"""
Module to handle resource settings definition to containers.
"""

from troposphere import Parameter
from troposphere import Sub, ImportValue
from troposphere.iam import Policy as IamPolicy

from ecs_composex.common import LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM


def generate_export_strings(res_name, attribute):
    """
    Function to generate the SSM and CFN import/export strings
    Returns the import in a tuple

    :param str res_name: name of the queue as defined in ComposeX File
    :param str|Parameter attribute: The attribute to use in Import Name.

    :returns: ImportValue for CFN
    :rtype: ImportValue
    """
    if isinstance(attribute, str):
        cfn_string = f"${{{ROOT_STACK_NAME_T}}}{DELIM}{res_name}{DELIM}{attribute}"
    elif isinstance(attribute, Parameter):
        cfn_string = (
            f"${{{ROOT_STACK_NAME_T}}}{DELIM}{res_name}{DELIM}{attribute.title}"
        )
    else:
        raise TypeError("Attribute can only be a string or Parameter")

    return ImportValue(Sub(cfn_string))


def generate_resource_permissions(resource_name, policies, attribute, arn=None):
    """
    Function to generate IAM permissions for a given x-resource. Returns the mapping of these for the given resource.

    :param str resource_name: The name of the resource
    :param str attribute: the attribute of the resource we are using for Import
    :param dict policies: the policies associated with the x-resource type.
    :param str arn: The ARN of the resource if already looked up.
    :return: dict of the IAM policies associated with the resource.
    :rtype dict:
    """
    resource_policies = {}
    for a_type in policies:
        clean_policy = {"Version": "2012-10-17", "Statement": []}
        LOG.debug(a_type)
        policy_doc = policies[a_type].copy()
        policy_doc["Sid"] = Sub(f"{a_type}To{resource_name}")
        policy_doc["Resource"] = (
            generate_export_strings(resource_name, attribute) if not arn else arn
        )
        clean_policy["Statement"].append(policy_doc)
        resource_policies[a_type] = IamPolicy(
            PolicyName=Sub(f"{a_type}{resource_name}${{{ROOT_STACK_NAME_T}}}"),
            PolicyDocument=clean_policy,
        )
    return resource_policies
