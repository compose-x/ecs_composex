#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from troposphere import If, NoValue

from ecs_composex.ecs.ecs_conditions import USE_FARGATE_CON_T


def reset_for_single_main_container(
    sidecar_used_memory: int, family: ComposeFamily, container_definition
) -> None:
    """
    When we have managed containers and a single application container, it is safe to
    assume that our managed sidecars have limits on CPU and RAM (because we defined it).
    In case we are then left with memory or CPU to spare, we want then to allow the final
    container of the task definition to have access to all the task remaining CPU and RAM

    If the container had memory limit and that is smaller than the memory that is left
    to use for a Fargate task, we set the limit as the new reservation.

    :param int sidecar_used_memory: The amount of RAM used by the sidecars
    :param ComposeFamily family: The family to update the settings for.
    """
    if isinstance(container_definition.Memory, int) and container_definition.Memory < (
        family.task_compute.fargate_ram - sidecar_used_memory
    ):
        setattr(
            container_definition,
            "MemoryReservation",
            If(USE_FARGATE_CON_T, (container_definition.Memory + 0), NoValue),
        )
    setattr(container_definition, "Memory", NoValue)
    setattr(container_definition, "Cpu", NoValue)


def handle_multi_services(sidecar_used_memory: int, family: ComposeFamily) -> None:
    """
    Identifies the essential containers. If there is only one, we assume that's the one
    that would make use of the left-over CPU/RAM from the Fargate profile

    :param int sidecar_used_memory:
    :param ComposeFamily family:
    """
    essential_containers = []
    containers_used_ram = 0
    for service in family.ordered_services:
        if service.container_definition.Essential is True:
            essential_containers.append(service.container_definition)
        else:
            containers_used_ram += (
                0
                if not isinstance(service.container_definition.Memory, int)
                else service.container_definition.Memory
            )
    if len(essential_containers) == 1:
        reset_for_single_main_container(
            (sidecar_used_memory + containers_used_ram),
            family,
            essential_containers[0],
        )


def unlock_compute_for_main_container(family: ComposeFamily) -> None:
    """
    When adding new containers (i.e. AppMesh/XRay etc.) the task definition CPU
    and RAM got bumped with these resources, the task CPU/Memory could have been
    bumped to the next Fargate profile. This results into waste of resource for
    a given service.

    This aims to identify the main service running in the family and grant it to us
    all unreserved CPU/RAM of the task

    :param family:
    """
    if len(family.ordered_services) == 1 and not family.managed_sidecars:
        reset_for_single_main_container(
            0, family, family.ordered_services[0].container_definition
        )
        return
    sidecar_used_memory = 0
    for _svc in family.managed_sidecars:
        if isinstance(_svc.container_definition.Memory, int):
            sidecar_used_memory += _svc.container_definition.Memory

    if family.ordered_services and family.managed_sidecars:
        if len(family.ordered_services) == 1:
            reset_for_single_main_container(
                sidecar_used_memory,
                family,
                family.ordered_services[0].container_definition,
            )
        else:
            handle_multi_services(sidecar_used_memory, family)
