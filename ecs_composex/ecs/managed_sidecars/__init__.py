#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.cfn_params import Parameter

from troposphere import Ref, Region

from ecs_composex.common.logging import LOG
from ecs_composex.compose.compose_services import ComposeService


class ManagedSidecar(ComposeService):
    def __init__(
        self,
        name,
        definition,
        is_essential: bool = False,
        image_param: Parameter = None,
        volumes: list = None,
    ):
        super().__init__(name, definition, image_param=image_param, volumes=volumes)
        self.is_essential = is_essential
        self.is_aws_sidecar = True

    def add_to_family(self, family: ComposeFamily, is_dependency: bool = False) -> None:
        """
        Adds the container as a sidecar to the family in order to fulfil a specific purpose
        for an AWS Feature, here, add xray-daemon for dynamic tracing.

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        :param bool is_dependency: Whether the family services depend on sidecar or not.
        """
        self.family = family
        family.add_managed_sidecar(self)
        self.set_as_dependency_to_family_services(is_dependency)
        if (
            family.logging
            and self not in family.logging.services_logging
            and not self.logging
        ):
            family.logging.set_init_family_service_logging(
                self,
                {
                    "awslogs-group": Ref(family.logging.family_log_group),
                    "awslogs-region": Region,
                    "awslogs-stream-prefix": self.name,
                },
            )
        self.define_port_mappings()
        self.family.service_networking.merge_services_ports()

    def set_as_dependency_to_family_services(self, is_dependency: bool = False) -> None:
        """
        Function to update the depends_on list for the family main services

        :param bool is_dependency: Whether the family services depend on sidecar or not.
        """
        for service in self.family.ordered_services:
            if is_dependency:
                if self.name not in service.depends_on:
                    service.depends_on.append(self.name)
                    LOG.info(
                        f"{self.family.name}.{service.name} - Added {self.name} as startup dependency"
                    )
            else:
                if service.name not in self.depends_on:
                    self.depends_on.append(service.name)
                    LOG.info(
                        f"{self.family.name}.{self.name} - Added {service.name} as startup dependency"
                    )
