#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from ecs_composex.common import LOG, add_parameters
from ecs_composex.compose.compose_services import ComposeService


class ManagedSidecar(ComposeService):
    def __init__(self, name, definition):
        super().__init__(name, definition)
        self.is_essential = False
        self.is_aws_sidecar = True

    def add_to_family(self, family: ComposeFamily, is_dependency: bool = False) -> None:
        """
        Adds the container as a sidecar to the family in order to fulfil a specific purpose
        for an AWS Feature, here, add xray-daemon for dynamic tracing.

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        :param bool is_dependency: Whether the family services depend on sidecar or not.
        """
        self.my_family = family
        family.add_managed_sidecar(self)
        self.set_parameters()
        self.set_as_dependency_to_family_services(is_dependency)

    def set_parameters(self) -> None:
        """
        Auto adds the sidecar container image as parameter to the stack
        """
        if self.my_family.template and self.my_family.stack and self.image_param:
            add_parameters(self.my_family.template, [self.image_param])

    def set_as_dependency_to_family_services(self, is_dependency: bool = False) -> None:
        """
        Function to update the depends_on list for the family main services

        :param bool is_dependency: Whether the family services depend on sidecar or not.
        """
        for service in self.my_family.ordered_services:
            if service.is_aws_sidecar:
                continue
            if is_dependency:
                if self.name not in service.depends_on:
                    service.depends_on.append(self.name)
                    LOG.info(
                        f"{self.my_family.name}.{service.name} - Added {self.name} as startup dependency"
                    )
            else:
                if service.name not in self.depends_on:
                    self.depends_on.append(service.name)
                    LOG.info(
                        f"{self.my_family.name}.{self.name} - Added {service.name} as startup dependency"
                    )
