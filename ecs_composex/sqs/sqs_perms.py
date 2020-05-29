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
based on pre-defined SQS policies for consumers
"""

from troposphere import Sub, ImportValue, If
from troposphere.ecs import Environment
from troposphere.iam import Policy as IamPolicy

from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common import keyisset
from ecs_composex.common import LOG
from ecs_composex.common.cfn_conditions import USE_SSM_ONLY_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.sqs import sqs_params
from ecs_composex.sqs.sqs_params import SQS_SSM_PREFIX

QUEUES_ACCESS_TYPES = {
    "RWMessages": {
        "NotAction": [
            "sqs:TagQueue",
            "sqs:RemovePermission",
            "sqs:AddPermission",
            "sqs:UntagQueue",
            "sqs:PurgeQueue",
            "sqs:DeleteQueue",
            "sqs:CreateQueue",
            "sqs:SetQueueAttributes",
        ],
        "Effect": "Allow",
    },
    "RWPermissions": {
        "NotAction": [
            "sqs:RemovePermission",
            "sqs:AddPermission",
            "sqs:PurgeQueue",
            "sqs:SetQueueAttributes",
        ],
        "Effect": "Allow",
    },
    "RO": {
        "NotAction": [
            "sqs:TagQueue",
            "sqs:RemovePermission",
            "sqs:AddPermission",
            "sqs:UntagQueue",
            "sqs:PurgeQueue",
            "sqs:Delete*",
            "sqs:Create*",
            "sqs:Set*",
        ],
        "Effect": "Allow",
    },
}


def generate_queue_strings(queue_name):
    """
    Function to generate the SSM and CFN import/export strings
    Returns the import in a tuple

    :param queue_name: name of the queue as defined in ComposeX File
    :type queue_name:

    :returns: tuple(ssm_export, cfn_export)
    :rtype: tuple(Sub, ImportValue)
    """
    ssm_string = f"/${{{ROOT_STACK_NAME_T}}}{SQS_SSM_PREFIX}{queue_name}"
    ssm_export = Sub(r"{{resolve:ssm:%s:1}}" % (ssm_string))
    cfn_string = (
        f"${{{ROOT_STACK_NAME_T}}}{DELIM}{queue_name}{DELIM}{sqs_params.SQS_ARN_T}"
    )
    cfn_import = ImportValue(Sub(cfn_string))
    return (ssm_export, cfn_import)


def generate_sqs_permissions(queue_name, resource, **kwargs):
    """
    Generates an IAM policy for each access type and returns a dictionnary of these.

    :params queue_name: String of the name of the queue as defined in Docker compose
    :type queue_name: str
    :param resource: The Troposphere resource
    :type resource: dict
    :param config: Dictionnary containing the configuration for rendering the permissions
    :type config: dict

    :returns: Dictionnary of IAM policies (PolicyType)
    :rtype: dict
    """

    export_strings = generate_queue_strings(queue_name)
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
            PolicyName=Sub(f"AccessToSqsQueue{queue_name}In${{{ROOT_STACK_NAME_T}}}"),
            PolicyDocument=clean_policy,
        )
    return queue_policies


def generate_sqs_envvars(queue_name, resource, **kwargs):
    """
    Function to generate environment variables that can be added to a container definition
    shall the ecs_service need to know about the Queue
    :return: environment key/pairs
    :rtype: list<troposphere.ecs.Environment>
    """
    env_names = []
    export_strings = generate_queue_strings(queue_name)
    if keyisset("Settings", resource) and keyisset("EnvNames", resource["Settings"]):
        for env_name in resource["Settings"]["EnvNames"]:
            env_names.append(
                Environment(
                    Name=env_name,
                    Value=If(USE_SSM_ONLY_T, export_strings[0], export_strings[1]),
                )
            )
        if queue_name not in resource["Settings"]["EnvNames"]:
            env_names.append(
                Environment(
                    Name=queue_name,
                    Value=If(USE_SSM_ONLY_T, export_strings[0], export_strings[1]),
                )
            )
    else:
        env_names.append(
            Environment(
                Name=queue_name,
                Value=If(USE_SSM_ONLY_T, export_strings[0], export_strings[1]),
            )
        )
    return env_names
