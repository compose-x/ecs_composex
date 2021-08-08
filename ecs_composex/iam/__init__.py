#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


import re

from troposphere import Join, Ref, Sub
from troposphere.iam import Role

from ecs_composex.common import LOG

ROLE_ARN_ARG = "RoleArn"


def service_role_trust_policy(service_name):
    """
    Simple function to format the trust relationship for a Role and an AWS Service
    used from lambda-my-aws/ozone

    :param service_name: name of the ecs_service
    :type service_name: str

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


def define_iam_policy(policy):
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


def add_role_boundaries(iam_role, policy):
    """
    Function to set permission boundary onto an IAM role

    :param iam_role: the IAM Role to add the boundary to
    :type iam_role: troposphere.iam.Role
    :param policy: the name or ARN of the policy
    :type policy: str
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
