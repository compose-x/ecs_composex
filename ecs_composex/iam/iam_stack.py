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

from ecs_composex.common import add_outputs, add_parameters, build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import CLUSTER_NAME

from .iam_ecs_helpers import add_ecs_execution_role_managed_policy, import_family_roles


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
            self.stack_template.add_resource(role.cfn_resource)
            role.stack = self
            if not role.attributes_outputs:
                role.generate_outputs()
            add_outputs(stack_template, role.outputs)
