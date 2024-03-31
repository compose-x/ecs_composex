#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@compose-x.io>

"""Functions to finalize the family compute & scaling settings"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily


def finalize_family_compute(family: ComposeFamily) -> None:
    """Finalizes the family compute settings"""
    family.add_containers_images_cfn_parameters()
    family.task_compute.set_task_compute_parameter()
    family.task_compute.unlock_compute_for_main_container()
    if family.service_compute.ecs_capacity_providers:
        family.service_compute.apply_capacity_providers_to_service(
            family.service_compute.ecs_capacity_providers
        )


def finalize_scaling_settings(family: ComposeFamily) -> None:
    """If family has scaling target configured, ensures that the scalable target gets created."""
    if (
        family.service_definition
        and family.service_definition.title in family.template.resources
    ) and (
        family.service_scaling
        and family.service_scaling.scalable_target
        and family.service_scaling.scalable_target.title
        not in family.template.resources
    ):
        family.template.add_resource(family.service_scaling.scalable_target)
