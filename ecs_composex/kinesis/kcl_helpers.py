# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2023 John Mille <john@compose-x.io>

"""Module to help with KCL IAM Permissions configuration to the services"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from .kinesis_stack import Stream

from compose_x_common.compose_x_common import keyisset
from troposphere import Sub
from troposphere.iam import PolicyType

from ecs_composex.common.troposphere_tools import add_resource


def add_cloudwatch_metric_data_permission(family: ComposeFamily) -> None:
    """
    Adds permissions to publish metrics data to CloudWatch
    """
    policy_title = f"{family.logical_name}Tocloudwatch"
    if policy_title not in family.iam_manager.iam_modules_policies:
        policy = PolicyType(
            policy_title,
            PolicyName=policy_title,
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "CloudwatchKCL",
                        "Effect": "Allow",
                        "Action": ["cloudwatch:PutMetricData"],
                        "Resource": ["*"],
                    }
                ],
            },
            Roles=family.iam_manager.task_role.name,
        )
        family.iam_manager.iam_modules_policies.update({"CloudwatchKCL": policy})
        add_resource(family.template, policy)
    else:
        cw_policy = family.template.resources[policy_title]
        statements = cw_policy.PolicyDocument["Statement"]
        for _statement in statements:
            if "Sid" in _statement and _statement["Sid"] == "CloudwatchKCL":
                break
        else:
            statements.append(
                {
                    "Sid": "CloudwatchKCL",
                    "Effect": "Allow",
                    "Action": ["cloudwatch:PutMetricData"],
                    "Resource": ["*"],
                }
            )


def define_dynamodb_statement(dynamodb_definition: Union[bool, dict]) -> list:
    sid = "DynamodbKCL"
    if isinstance(dynamodb_definition, bool):
        statement = [
            {
                "Sid": sid,
                "Action": ["dynamodb:*"],
                "Effect": "Allow",
                "Resource": ["*"],
            }
        ]
    elif isinstance(dynamodb_definition, dict):
        if keyisset("EnableCreateDeleteTables", dynamodb_definition):
            actions = ["dynamodb:*"]
        else:
            actions = [
                f"dynamodb:{_action}"
                for _action in [
                    "DescribeTable, GetItem, PutItem, Scan, UpdateItem",
                    "DeleteItem",
                ]
            ]
        if keyisset("TableNames", dynamodb_definition):
            resource = [
                Sub(
                    f"arn:${{AWS::Partition}}:dynamodb:*:${{AWS::AccountId}}:table/{table}"
                )
                for table in dynamodb_definition["TableNames"]
            ]
        else:
            resource = ["*"]
        statement = [
            {
                "Effect": "Allow",
                "Sid": sid,
                "Resource": resource,
                "Action": actions,
            }
        ]
    else:
        raise TypeError(
            f"dynamodb_definition is {type(dynamodb_definition)}. Expected one of",
            [bool, dict],
        )
    return statement


def add_dynamodb_permissions(
    family: ComposeFamily, dynamodb_definition: Union[bool, dict]
) -> None:
    """
    Adds permissions to access DynamoDB
    If is boolean, grant all default access to DynamoDB
    If is dict, applies permissions based on the settings defined by user
    """

    resource_module = "dynamodb"
    policy_title = f"{family.logical_name}To{resource_module}"
    statement = define_dynamodb_statement(dynamodb_definition)
    if resource_module not in family.iam_manager.iam_modules_policies:
        policy = PolicyType(
            policy_title,
            PolicyName=policy_title,
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": statement,
            },
        )
        family.iam_manager.iam_modules_policies.update({resource_module: policy})
        add_resource(family.template, policy)
    else:
        policy = family.template.resources[policy_title]
        statements = policy.PolicyDocument["Statement"]
        for _statement in statements:
            if keyisset("Sid", _statement) and _statement["Sid"] == "DynamodbKCL":
                break
        else:
            statements.append(statement)
