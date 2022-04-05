#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere.iam import Policy


def add_policies_from_x_iam(task_policies: list, new_policies: list):
    """
    Add IAM Policies to a list if not already defined.

    :param list[Policy] task_policies:
    :param list[dict] new_policies:
    :return:
    """
    existing_policy_names = [policy.PolicyName for policy in task_policies]
    for count, policy in enumerate(new_policies):
        generated_name = (
            f"PolicyGenerated{count}"
            if f"PolicyGenerated{count}" not in existing_policy_names
            else f"PolicyGenerated{count + len(existing_policy_names)}"
        )
        name = (
            generated_name
            if not keyisset("PolicyName", policy)
            else policy["PolicyName"]
        )
        if name not in existing_policy_names:
            policy_object = Policy(
                PolicyName=name, PolicyDocument=policy["PolicyDocument"]
            )
            task_policies.append(policy_object)


def set_update_managed_policies(role, new_policies: list) -> None:
    """
    Sets or adds ManagedPolicyArns to the IAM Role
    :param troposphere.iam.Role role:
    :param new_policies:
    :return:
    """
    try:
        managed_policies = getattr(role, "ManagedPolicyArns")
    except (KeyError, AttributeError):
        setattr(role, "ManagedPolicyArns", [])
        managed_policies = getattr(role, "ManagedPolicyArns")
    unique_new_polcies = list(set(new_policies))
    managed_policies += [
        policy for policy in unique_new_polcies if policy not in managed_policies
    ]


def set_update_inline_policies(role, new_policies: list) -> None:
    """
    Adds new inline policies in the role Policies

    :param role:
    :param new_policies:
    :return:
    """
    try:
        policies = getattr(role, "Policies")
    except (KeyError, AttributeError):
        setattr(role, "Policies", [])
        policies = getattr(role, "Policies")
    unique_new_polcies = list(set(new_policies))
    policies += [policy for policy in unique_new_polcies if policy not in policies]
