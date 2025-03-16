#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack

from compose_x_common.compose_x_common import set_else_none
from troposphere import AWS_NO_VALUE, Ref

from ecs_composex.common.troposphere_tools import add_outputs, add_resource
from ecs_composex.elbv2.elbv2_ecs.common import setup_template
from ecs_composex.elbv2.elbv2_ecs.target_helpers import (
    import_target_group_attributes,
    set_healthcheck_definition,
)
from ecs_composex.elbv2.resources.merged_target_group import MergedTargetGroup
from ecs_composex.vpc.vpc_params import VPC_ID


def handle_target_groups_association(
    load_balancer: Elbv2, res_root_stack: ComposeXStack, settings: ComposeXSettings
) -> None:
    """
    Function to create TargetGroups based on the `TargetGroups` defined on the ELB rather than the services.
    This allows to associate more than one ECS service to a single TargetGroup.
    """
    template: Template = setup_template(load_balancer, res_root_stack)
    _targets = set_else_none("TargetGroups", load_balancer.definition, {})
    if not _targets:
        return
    for _target_name, _target_def in _targets.items():
        props = {}
        set_healthcheck_definition(props, _target_def, "HealthCheck")
        props["Port"] = _target_def["Port"]
        props["Protocol"] = _target_def["Protocol"]
        props["ProtocolVersion"] = set_else_none(
            "ProtocolVersion", _target_def, Ref(AWS_NO_VALUE)
        )
        props["TargetType"] = "ip"
        import_target_group_attributes(props, _target_def, load_balancer)
        _tgt_group = MergedTargetGroup(
            _target_name,
            _target_def,
            load_balancer,
            load_balancer.stack,
            int(_target_def["Port"]),
            VpcId=Ref(VPC_ID),
            **props,
        )
        _tgt_group.init_outputs()
        _tgt_group.generate_outputs()
        add_resource(template, _tgt_group)
        add_outputs(template, _tgt_group.outputs)
        load_balancer.target_groups.append(_tgt_group)
        _tgt_group.associate_families(settings)

        for listener in load_balancer.new_listeners:
            listener.map_target_group_to_listener(_tgt_group)

        for listener in load_balancer.lookup_listeners.values():
            listener.map_target_group_to_listener(_tgt_group)
    set_target_group_listeners(load_balancer, res_root_stack, template, settings)


def set_target_group_listeners(
    load_balancer: Elbv2,
    res_root_stack: ComposeXStack,
    template: Template,
    settings: ComposeXSettings,
) -> None:

    for listener_port, listener_def in load_balancer.lookup_listeners.items():
        print(listener_port, listener_def)

    for listener in load_balancer.new_listeners:
        listener.handle_certificates(settings, res_root_stack)
        listener.handle_cognito_pools(settings, res_root_stack)
        listener.define_default_actions(load_balancer, template)
