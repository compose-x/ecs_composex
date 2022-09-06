#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
IAM Stack that will create all the ComposeFamily IAM Roles and managed policies.
Using that as a primary dependency allows to ensure IAM roles creation is successful
before moving on to creating other resources.

At the moment, only cares for the IAM Roles of services, will down the road handle IAM roles
for RDS and other resources that have IAM based features.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

from collections import OrderedDict

from compose_x_common.compose_x_common import keyisset
from troposphere import NoValue, Sub
from troposphere.iam import Role as IamRole

from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
    build_template,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.iam import define_iam_policy, service_role_trust_policy

from .iam_ecs_helpers import add_ecs_execution_role_managed_policy, import_family_roles


class ResourceIamManager:
    """
    Class to bundle up IAM role and permissions for a given AWS Resource.
    """

    def __init__(self, resource, linked_service_name):
        self._resource = resource
        self.iam_modules_policies = OrderedDict()
        self.permissions_boundary = NoValue
        if (
            resource.parameters
            and keyisset("x-iam", resource.parameters)
            and keyisset("PermissionsBoundary", resource.parameters["x-iam"])
        ):
            self.permissions_boundary = define_iam_policy(
                resource.parameters["x-iam"]["PermissionsBoundary"]
            )
        self.service_linked_role = IamRole(
            f"{resource.logical_name}IamRole",
            AssumeRolePolicyDocument=service_role_trust_policy(linked_service_name),
            Description=Sub(
                f"Firehose IAM Service Role for {resource.logical_name} - ${{STACK_NAME}}",
                STACK_NAME=define_stack_name(),
            ),
            PermissionsBoundary=self.permissions_boundary,
        )

    @property
    def resource(self):
        return self._resource


class XStack(ComposeXStack):
    """
    Class to represent the IAM top stack
    """

    def __init__(self, name: str, settings: ComposeXSettings, **kwargs):
        stack_template = build_template("Root stack for IAM Roles")
        add_parameters(stack_template, [CLUSTER_NAME])
        super().__init__(name, stack_template, **kwargs)
        exec_role_managed_policy = add_ecs_execution_role_managed_policy(stack_template)
        self.Parameters.update(
            {CLUSTER_NAME.title: settings.ecs_cluster.cluster_identifier}
        )
        new_roles = import_family_roles(settings, exec_role_managed_policy)
        for role in new_roles:
            add_resource(stack_template, role.cfn_resource)
            role.stack = self
            if not role.attributes_outputs:
                role.generate_outputs()
            add_outputs(stack_template, role.outputs)
