# -*- coding: utf-8 -*-
"""
Set of functions to generate permissions to access queues
based on pre-defined SQS policies for consumers
"""

from troposphere import Sub, ImportValue, If
from troposphere.iam import Policy as IamPolicy
from troposphere.ecs import Environment
from ecs_composex.sqs import sqs_params
from ecs_composex.common import LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.cfn_conditions import USE_SSM_ONLY_T
from ecs_composex.common import KEYISSET
from ecs_composex.sqs import SQS_SSM_PREFIX

QUEUES_ACCESS_TYPES = {
    'RWMessages': {
        "NotAction": [
            "sqs:TagQueue",
            "sqs:RemovePermission",
            "sqs:AddPermission",
            "sqs:UntagQueue",
            "sqs:PurgeQueue",
            "sqs:DeleteQueue",
            "sqs:CreateQueue",
            "sqs:SetQueueAttributes"
        ],
        "Effect": "Allow"
    },
    'RWPermissions': {
        "NotAction": [
            "sqs:RemovePermission",
            "sqs:AddPermission",
            "sqs:PurgeQueue",
            "sqs:SetQueueAttributes"
        ],
        "Effect": "Allow"
    },
    'RO': {
        "NotAction": [
            "sqs:TagQueue",
            "sqs:RemovePermission",
            "sqs:AddPermission",
            "sqs:UntagQueue",
            "sqs:PurgeQueue",
            "sqs:Delete*",
            "sqs:Create*",
            "sqs:Set*"
        ],
        "Effect": "Allow"
    }
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
    ssm_export = Sub(r'{{resolve:ssm:%s:1}}' % (ssm_string))
    cfn_string = f"${{{ROOT_STACK_NAME_T}}}-{queue_name}-{sqs_params.SQS_ARN_T}"
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
    services = resource['Services']
    for a_type in QUEUES_ACCESS_TYPES:
        clean_policy = {'Version': '2012-10-17', 'Statement': []}
        LOG.debug(a_type)
        policy_doc = QUEUES_ACCESS_TYPES[a_type].copy()
        policy_doc['Resource'] = If(
            USE_SSM_ONLY_T,
            export_strings[0],
            export_strings[1]
        )
        clean_policy['Statement'].append(policy_doc)
        queue_policies[a_type] = {
            'Services': [],
            'Policy': None
        }
        queue_policies[a_type]['Policy'] = IamPolicy(
            PolicyName=Sub(f"AccessToSqsQueue{queue_name}In${{{ROOT_STACK_NAME_T}}}"),
            PolicyDocument=clean_policy
        )
        for service in services:
            if service['access'] == a_type:
                queue_policies[a_type]['Services'].append(service['name'])
    return queue_policies


def generate_sqs_envvars(queue_name, resource, **kwargs):
    """
    Function to generate environment variables that can be added to a container definition
    shall the service need to know about the Queue
    """
    env_names = []
    export_strings = generate_queue_strings(queue_name)
    if KEYISSET('Settings', resource) and KEYISSET('EnvNames', resource['Settings']):
        for env_name in resource['Settings']['EnvNames']:
            env_names.append(Environment(
                    Name=env_name,
                    Value=If(
                            USE_SSM_ONLY_T,
                            export_strings[0],
                            export_strings[1]
                        )
                )
            )
        if queue_name not in resource['Settings']['EnvNames']:
            env_names.append(Environment(
                    Name=queue_name,
                    Value=If(
                            USE_SSM_ONLY_T,
                            export_strings[0],
                            export_strings[1]
                        )
                )
            )
    return env_names
