# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG
from ecs_composex.elbv2.elbv2_ecs.handle_service_association import (
    handle_services_association,
)
from ecs_composex.elbv2.elbv2_ecs.handle_target_groups import (
    handle_target_groups_association,
)


def elbv2_to_ecs(
    resources: dict,
    services_stack: ComposeXStack,
    res_root_stack: ComposeXStack,
    settings: ComposeXSettings,
) -> None:
    """
    Entrypoint function to map services, targets, listeners and ACM together.

    Args:
        resources: Dictionary of resources to process
        services_stack: ComposeX stack for services
        res_root_stack: Root ComposeX stack
        settings: ComposeX settings
    """

    def process_resource(resource_name: str, resource, lookup: bool = False) -> None:
        resource_type = "(Lookup)" if lookup else ""
        has_target_groups = keyisset("TargetGroups", resource.definition)

        link_type = "TargetGroups" if has_target_groups else "Services"
        LOG.info(
            f"{resource.module.res_key}.{resource_name} {resource_type} - "
            f"Linking to {link_type}"
        )

        handler = (
            handle_target_groups_association
            if has_target_groups
            else handle_services_association
        )
        handler(resource, res_root_stack, settings)

    for resource_name, resource in resources.items():
        if resource.cfn_resource or resource.mappings:
            process_resource(resource_name, resource, lookup=bool(resource.mappings))
