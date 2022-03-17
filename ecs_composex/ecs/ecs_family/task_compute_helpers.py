#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere import Ref

from ecs_composex.compose.compose_services.docker_tools import (
    find_closest_fargate_configuration,
)
from ecs_composex.ecs.ecs_params import FARGATE_CPU_RAM_CONFIG_T


def set_task_compute_parameter(family):
    """
    Method to update task parameter for CPU/RAM profile
    """
    for service in family.services:
        if isinstance(service.container_definition.Cpu, int):
            family.task_cpu += service.container_definition.Cpu
        if isinstance(service.container_definition.Memory, int) and isinstance(
            service.container_definition.MemoryReservation, int
        ):
            family.task_memory += max(
                service.container_definition.Memory,
                service.container_definition.MemoryReservation,
            )
        elif isinstance(service.container_definition.Memory, Ref) and isinstance(
            service.container_definition.MemoryReservation, int
        ):
            family.task_memory += service.container_definition.MemoryReservation
        elif isinstance(service.container_definition.Memory, int) and isinstance(
            service.container_definition.MemoryReservation, Ref
        ):
            family.task_memory += service.container_definition.Memory

    if family.task_cpu > 0 or family.task_memory > 0:
        cpu_ram = find_closest_fargate_configuration(
            family.task_cpu, family.task_memory, True
        )
        family.stack_parameters.update({FARGATE_CPU_RAM_CONFIG_T: cpu_ram})
