# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>


import re

from troposphere import Join, Ref, Sub
from troposphere.iam import Role

from ecs_composex.common.logging import LOG

ROLE_ARN_ARG = "RoleArn"


def service_role_trust_policy(service_name: str) -> dict:
    """
    Simple function to format the trust relationship for a Role and an AWS Service
    used from lambda-my-aws/ozone

    :param str service_name: name of the ecs_service
    :return: policy document
    :rtype: dict
    """
    statement = {
        "Effect": "Allow",
        "Principal": {"Service": [Sub(f"{service_name}.${{AWS::URLSuffix}}")]},
        "Action": ["sts:AssumeRole"],
        "Condition": {"Bool": {"aws:SecureTransport": "true"}},
    }
    policy_doc = {"Version": "2012-10-17", "Statement": [statement]}
    return policy_doc


def define_iam_policy(policy: str) -> str:
    """
    From input, determines if the policy string is the full ARN or just the name of the policy.
    If just the name, assumes it is from the account itself, and adds the necessary ARN prefix.

    :param str policy:
    :return: the policy
    :rtype: str
    """
    policy_def = policy
    policy_re = re.compile(
        r"((^([a-zA-Z0-9-_./]+)$)|(^(arn:aws:iam::(aws|\d{12}):policy/)[a-zA-Z0-9-_./]+$))"
    )

    if not policy_re.match(policy):
        raise ValueError(
            f"policy name {policy} does not match expected regexp",
            policy_re.pattern,
        )
    if isinstance(policy, str) and not policy.startswith("arn:aws:iam::"):
        policy_def = Sub(
            f"arn:${{AWS::Partition}}:iam::${{AWS::AccountId}}:policy/{policy}"
        )
    elif isinstance(policy, (Sub, Ref, Join)):
        LOG.debug(f"policy {policy}")
    return policy_def


def add_role_boundaries(iam_role: Role, policy: str) -> None:
    """
    Function to set permission boundary onto an IAM role

    :param troposphere.iam.Role iam_role: the IAM Role to add the boundary to
    :param str policy: the name or ARN of the policy
    """
    if not isinstance(iam_role, Role):
        raise TypeError(f"{iam_role} is of type", type(iam_role), "expected", Role)
    if isinstance(policy, str):
        policy = define_iam_policy(policy)
    if hasattr(iam_role, "PermissionsBoundary"):
        LOG.warning(
            f"IAM Role {iam_role.title} already has PermissionsBoundary set. Overriding"
        )
    setattr(iam_role, "PermissionsBoundary", policy)
