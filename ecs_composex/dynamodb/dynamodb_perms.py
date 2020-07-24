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
Set of functions to generate permissions to access queues
based on pre-defined TABLE policies for consumers
"""

from troposphere import Sub, ImportValue, If
from troposphere.ecs import Environment
from troposphere.iam import Policy as IamPolicy

from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common import keyisset
from ecs_composex.common import LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.cfn_conditions import USE_SSM_ONLY_T
from ecs_composex.dynamodb import dynamodb_params

QUEUES_ACCESS_TYPES = {
    "RW": {
        "Action": [
            "dynamodb:BatchGet*",
            "dynamodb:DescribeStream",
            "dynamodb:DescribeTable",
            "dynamodb:Get*",
            "dynamodb:Query",
            "dynamodb:Scan",
            "dynamodb:BatchWrite*",
            "dynamodb:DeleteItem",
            "dynamodb:UpdateItem",
            "dynamodb:PutItem",
        ],
        "Effect": "Allow",
    },
    "RO": {
        "Action": ["dynamodb:DescribeTable", "dynamodb:Query", "dynamodb:Scan"],
        "Effect": "Allow",
    },
    "PowerUser": {
        "NotAction": [
            "dynamodb:CreateTable",
            "dynamodb:DeleteTable",
            "dynamodb:DeleteBackup",
        ]
    },
}


def generate_queue_strings(table_name):
    """
    Function to generate the SSM and CFN import/export strings
    Returns the import in a tuple

    :param table_name: name of the queue as defined in ComposeX File
    :type table_name:

    :returns: tuple(ssm_export, cfn_export)
    :rtype: tuple(Sub, ImportValue)
    """
    ssm_string = (
        f"/${{{ROOT_STACK_NAME_T}}}{dynamodb_params.TABLE_SSM_PREFIX}{table_name}"
    )
    ssm_export = Sub(r"{{resolve:ssm:%s:1}}" % ssm_string)
    cfn_string = f"${{{ROOT_STACK_NAME_T}}}{DELIM}{table_name}{DELIM}{dynamodb_params.TABLE_ARN_T}"
    cfn_import = ImportValue(Sub(cfn_string))
    return ssm_export, cfn_import


def generate_dynamodb_permissions(table_name):
    """
    Generates an IAM policy for each access type and returns a dictionnary of these.

    :params table_name: String of the name of the queue as defined in Docker compose
    :type table_name: str
    :param config: Dictionnary containing the configuration for rendering the permissions
    :type config: dict

    :returns: Dictionnary of IAM policies (PolicyType)
    :rtype: dict
    """

    export_strings = generate_queue_strings(table_name)
    queue_policies = {}
    for a_type in QUEUES_ACCESS_TYPES:
        clean_policy = {"Version": "2012-10-17", "Statement": []}
        LOG.debug(a_type)
        policy_doc = QUEUES_ACCESS_TYPES[a_type].copy()
        policy_doc["Resource"] = If(
            USE_SSM_ONLY_T, export_strings[0], export_strings[1]
        )
        clean_policy["Statement"].append(policy_doc)
        queue_policies[a_type] = IamPolicy(
            PolicyName=Sub(f"AccessTo{table_name}In${{{ROOT_STACK_NAME_T}}}"),
            PolicyDocument=clean_policy,
        )
    return queue_policies


def generate_dynamodb_envvars(table_name, resource):
    """
    Function to generate environment variables that can be added to a container definition
    shall the ecs_service need to know about the Queue
    :return: environment key/pairs
    :rtype: list<troposphere.ecs.Environment>
    """
    env_names = []
    export_strings = generate_queue_strings(table_name)
    if keyisset("Settings", resource) and keyisset("EnvNames", resource["Settings"]):
        for env_name in resource["Settings"]["EnvNames"]:
            env_names.append(
                Environment(
                    Name=env_name,
                    Value=If(USE_SSM_ONLY_T, export_strings[0], export_strings[1]),
                )
            )
        if table_name not in resource["Settings"]["EnvNames"]:
            env_names.append(
                Environment(
                    Name=table_name,
                    Value=If(USE_SSM_ONLY_T, export_strings[0], export_strings[1]),
                )
            )
    else:
        env_names.append(
            Environment(
                Name=table_name,
                Value=If(USE_SSM_ONLY_T, export_strings[0], export_strings[1]),
            )
        )
    return env_names
