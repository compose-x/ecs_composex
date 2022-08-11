#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from itertools import chain

from troposphere import If, NoValue

from ecs_composex.common.logging import LOG
from ecs_composex.compose.compose_services.docker_tools import (
    find_closest_fargate_configuration,
)
from ecs_composex.ecs.ecs_conditions import USE_FARGATE_CON_T
from ecs_composex.ecs.ecs_params import (
    FARGATE_CPU,
    FARGATE_CPU_RAM_CONFIG_T,
    FARGATE_RAM,
)

from .helpers import unlock_compute_for_main_container


class TaskCompute:
    """
    Class to handle task and services compute settings (CPU/RAM)
    """

    def __init__(self, family: ComposeFamily):
        self.family = family
        self._raw_cpu = 0
        self._raw_ram = 0

        self._fargate_cpu = 0
        self._fargate_ram = 0

        self.fargate_cpu = 256
        self.fargate_ram = 512

        self._sidecar_used_cpu = 0
        self._sidecar_used_ram = 0

    @property
    def fargate_cpu(self):
        return self._fargate_cpu

    @fargate_cpu.setter
    def fargate_cpu(self, value):
        if value > 0:
            self._fargate_cpu = value
        elif value <= 0:
            raise ValueError("Fargate CPU must be a positive value")

    @property
    def fargate_ram(self):
        return self._fargate_ram

    @fargate_ram.setter
    def fargate_ram(self, value: int):
        if value > 0:
            self._fargate_ram = value
        elif value <= 0:
            raise ValueError("Fargate RAM must be a positive value")

    @property
    def family_cpu(self):
        return self._raw_cpu

    @property
    def cfn_family_cpu(self):
        if self._raw_cpu < 128:
            LOG.debug(
                f"{self.family.name} - Minimum CPU for task in ECS is 128. Got {self._raw_cpu}. Correcting"
            )
            return "128"
        return str(self._raw_cpu)

    @family_cpu.setter
    def family_cpu(self, value: int):
        self._raw_cpu = value
        if self.family.task_definition:
            setattr(
                self.family.task_definition,
                "Cpu",
                If(USE_FARGATE_CON_T, FARGATE_CPU, self.cfn_family_cpu),
            )

    @property
    def family_ram(self):
        return self._raw_ram

    @property
    def cfn_family_ram(self):
        if self._raw_ram < 128:
            LOG.debug(
                f"{self.family.name} - Minimum RAM for task in ECS is 128MB. Got {self._raw_ram}. Correcting"
            )
            return "128"
        return str(self._raw_ram)

    @family_ram.setter
    def family_ram(self, value: int):
        self._raw_ram = value
        if self.family.task_definition:
            setattr(
                self.family.task_definition,
                "Memory",
                If(USE_FARGATE_CON_T, FARGATE_RAM, self.cfn_family_ram),
            )

    def update_family_fargate(self, cpu, ram):
        self.fargate_cpu, self.fargate_ram = find_closest_fargate_configuration(
            cpu, ram
        )
        if self.family.stack:
            cpu_ram = f"{self.fargate_cpu}!{self.fargate_ram}"
            self.family.stack.Parameters.update({FARGATE_CPU_RAM_CONFIG_T: cpu_ram})

    def set_task_compute_parameter(self):
        """
        Method to update task parameter for CPU/RAM profile
        """
        math_cpu = 0
        math_ram = 0
        for service in chain(
            self.family.managed_sidecars, self.family.ordered_services
        ):
            if isinstance(service.container_definition.Cpu, int):
                math_cpu += service.container_definition.Cpu

            if (
                isinstance(service.container_definition.Memory, int)
                and service.container_definition.MemoryReservation == NoValue
            ):
                math_ram += service.container_definition.Memory

            elif service.container_definition.Memory == NoValue and isinstance(
                service.container_definition.MemoryReservation, int
            ):
                math_ram += service.container_definition.MemoryReservation
            elif isinstance(service.container_definition.Memory, int) and isinstance(
                service.container_definition.MemoryReservation, int
            ):
                if (
                    service.container_definition.MemoryReservation
                    > service.container_definition.Memory
                ):
                    raise ValueError(
                        f"{service.name} has more Memory reservations than limits"
                    )
                math_ram += service.container_definition.Memory

        self.family_cpu = math_cpu
        self.family_ram = math_ram
        self.update_family_fargate(math_cpu, math_ram)

    def unlock_compute_for_main_container(self):
        unlock_compute_for_main_container(self.family)
