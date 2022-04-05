#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Package managing the IAM resources (roles, policies etc.) for a given ComposeFamily
"""

from collections import OrderedDict

from compose_x_common.compose_x_common import set_else_none
from troposphere import Ref
from troposphere.iam import Policy

from ecs_composex.ecs.ecs_params import EXEC_ROLE_T, TASK_ROLE_T
from ecs_composex.iam import add_role_boundaries

from .helpers import (
    add_policies_from_x_iam,
    set_update_inline_policies,
    set_update_managed_policies,
)
from .task_role import EcsRole


class TaskIam:
    """
    Class to manage the compose family IAM roles, permissions and other settings
    """

    def __init__(self, family):
        self.family = family

        self.exec_role = EcsRole(self.family, EXEC_ROLE_T)
        self.task_role = EcsRole(self.family, TASK_ROLE_T)
        self.definition = {}
        self.managed_policies = []
        self.policies = []
        self._permissions_boundary = None
        self.iam_modules_policies = OrderedDict()
        self.init_update_policies()

    def __repr__(self):
        return f"{self.family.name}.x-iam"

    @property
    def managed_policies_list(self):
        return [policy for policy in self.managed_policies if isinstance(policy, str)]

    @property
    def inline_policies_names(self):
        return [p.PolicyName for p in self.policies if isinstance(p, Policy)]

    @property
    def permissions_boundary(self):
        return self._permissions_boundary

    @permissions_boundary.setter
    def permissions_boundary(self, value):
        self._permissions_boundary = value

    def init_update_policies(self):
        for service in self.family.services:
            managed_policies = set_else_none("ManagedPolicyArns", service.x_iam, [])
            if managed_policies:
                self.add_new_managed_policies(managed_policies)

            permissions_boundary = set_else_none(
                "PermissionsBoundary", service.x_iam, False
            )
            if permissions_boundary and not self.permissions_boundary:
                self.permissions_boundary = permissions_boundary
                add_role_boundaries(
                    self.exec_role.cfn_resource, self.permissions_boundary
                )
                add_role_boundaries(
                    self.task_role.cfn_resource, self.permissions_boundary
                )
            elif (
                permissions_boundary
                and self.permissions_boundary
                and permissions_boundary != self.permissions_boundary
            ):
                print(
                    f"{self.family} - Permissions boundary already set: {self.permissions_boundary}."
                    f" Cannot add {permissions_boundary}"
                    " as PermissionsBoundary is single string"
                )

            policies = set_else_none("Policies", service.x_iam, [])
            if policies:
                add_policies_from_x_iam(self.policies, policies)

        setattr(self.task_role.cfn_resource, "Policies", self.policies)

    def describe(self):
        print(
            self.family.name,
            "PermissionsBoundary",
            self.permissions_boundary,
            "ManagedPolicyArns",
            self.managed_policies_list,
            "Policies",
            self.inline_policies_names,
        )

    def get_role_from_name(self, role_name: str = None) -> EcsRole:
        if role_name is None:
            role_name = TASK_ROLE_T
        if role_name == EXEC_ROLE_T:
            role = self.exec_role
        else:
            role = self.task_role
        return role

    def add_new_managed_policies(self, policies: list, role_name: str = None):
        """
        Adds new managed policies to the given IAM role. If no role given, assume TaskRole

        :param list[str] policies:
        :param role_name: Allows overriding which role to assign the policies to.
        """
        set_update_managed_policies(
            self.get_role_from_name(role_name).cfn_resource, policies
        )

    def add_new_managed_policy(self, policy, role_name: str = None):
        """
        Adds new managed policies to the given IAM role. If no role given, assume TaskRole

        :param policy:
        :param role_name: Allows overriding which role to assign the policies to.
        """
        role = self.get_role_from_name(role_name).cfn_resource
        set_update_managed_policies(role, [policy])
        if isinstance(policy, Ref):
            try:
                role_depends_on = getattr(role, "DependsOn")
            except (KeyError, AttributeError):
                setattr(role, "DependsOn", [])
                role_depends_on = getattr(role, "DependsOn")
            role_depends_on.append(policy.data["Ref"])

    def add_new_policy(self, policy, role_name=None) -> None:
        """
        Adds new inline policy to the role

        :param policy:
        :param role_name:
        :return:
        """
        cfn_role = self.get_role_from_name(role_name).cfn_resource
        if isinstance(policy, Policy):
            set_update_inline_policies(cfn_role, [policy])
