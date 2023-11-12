# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to define the entry point for AWS Event Rules
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ecs_composex.events.events_helpers import create_events_template

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

import warnings

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.services_resources import ServicesXResource
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, FARGATE_VERSION


class Rule(ServicesXResource):
    """
    Class to define an Event Rule
    """

    def handle_families_targets_expansion_list(
        self, service_name: str, service_def: dict, settings: ComposeXSettings
    ):
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource
        """
        the_service = [s for s in settings.services if s.name == service_def["name"]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [
                            self.define_service_to_associate(
                                service_name, family_name, settings
                            )
                        ],
                        service_def["TaskCount"],
                        service_def,
                    )
                )

    def set_services_targets_from_list(self, settings: ComposeXSettings):
        """
        Override method to map services and families targets of the services defined specifically for
        events
        TargetStructure:
        (family, family_wide, services[], access)
        :return:
        """
        if not self.services:
            LOG.info(f"No services defined for {self.name}")
            return
        for service in self.services:
            service_name = service["name"]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service["TaskCount"],
                        service,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.warning(
                    f"The family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion_list(
                    service_name, service, settings
                )

    def handle_families_targets_expansion_dict(
        self, service_name: str, service_def: dict, settings: ComposeXSettings
    ) -> None:
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource
        """
        the_service = [s for s in settings.services if s.name == service_name][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [
                            self.define_service_to_associate(
                                service_name, family_name, settings
                            )
                        ],
                        service_def["TaskCount"],
                        service_def,
                    )
                )

    def set_services_targets_from_dict(self, settings: ComposeXSettings) -> None:
        """Deals with services set as a dict"""
        for service_name, service_def in self.services.items():
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service_def["TaskCount"],
                        service_def,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.debug(
                    f"{self.module.res_key}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion_dict(
                    service_name, service_def, settings
                )


class XStack(ComposeXStack):
    """
    Class to handle events stack
    """

    def __init__(
        self, title: str, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        """Initialize the XStack for Events"""
        if module.lookup_resources:
            warnings.warn(
                f"{module.res_key} does not support Lookup/Use. You can only create new resources"
            )

        if module.new_resources:
            stack_template = build_template(
                "Events rules for Compose-X",
                [CLUSTER_NAME, FARGATE_VERSION],
            )
            super().__init__(title, stack_template, **kwargs)
            create_events_template(self, settings, module.new_resources)
            if not hasattr(self, "DeletionPolicy"):
                setattr(self, "DeletionPolicy", module.module_deletion_policy)

        else:
            self.is_void = True
