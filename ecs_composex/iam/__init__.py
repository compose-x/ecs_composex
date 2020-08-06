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

"""Entrypoint for IAM"""

import re
from troposphere import Sub, Ref, Join
from troposphere.iam import Role

from ecs_composex.common import LOG

POLICY_PATTERN = r"((^([a-zA-Z0-9-_.\/]+)$)|(^(arn:aws:iam::(aws|[0-9]{12}):policy\/)[a-zA-Z0-9-_.\/]+$))"
POLICY_RE = re.compile(POLICY_PATTERN)


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
    if not POLICY_RE.match(policy):
        raise ValueError(
            f"policy name {policy} does not match expected regexp", POLICY_PATTERN
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
    policy = define_iam_policy(policy)
    if hasattr(iam_role, "PermissionsBoundary"):
        LOG.warn(
            f"IAM Role {iam_role.title} already has PermissionsBoundary set. Overriding"
        )
    setattr(iam_role, "PermissionsBoundary", policy)
