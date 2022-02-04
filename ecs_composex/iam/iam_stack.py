#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>


from ecs_composex.common import add_outputs, add_parameters, build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import CLUSTER_NAME


def import_family_roles(settings):
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    roles = []
    for family in settings.families.values():
        roles.append(family.task_role)
        roles.append(family.exec_role)
    return roles


class XStack(ComposeXStack):
    """
    Class to represent the IAM top stack
    """

    def __init__(self, name, settings, **kwargs):
        stack_template = build_template("Root stack for IAM Roles")
        add_parameters(stack_template, [CLUSTER_NAME])
        super().__init__(name, stack_template, **kwargs)
        self.Parameters.update(
            {CLUSTER_NAME.title: settings.ecs_cluster.cluster_identifier}
        )
        new_roles = import_family_roles(settings)
        for role in new_roles:
            self.stack_template.add_resource(role.cfn_resource)
            role.stack = self
            if not role.attributes_outputs:
                role.generate_outputs()
            add_outputs(stack_template, role.outputs)
