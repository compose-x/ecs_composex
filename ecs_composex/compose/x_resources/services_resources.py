#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import keyisset, set_else_none

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.compose.x_resources import XResource


class ServicesXResource(XResource):
    """
    Class for XResource that would be linked to services for IAM / Ingress

    :ivar list[tuple] families_targets: List of the service targets to associate access with
    :ivar list[tuple] families_scaling: List of the services target to associate scaling with
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        self.services = []
        self.families_targets: list[tuple] = []
        self.families_scaling = []
        self.arn_parameter = None
        super().__init__(name, definition, module, settings)
        self.services = set_else_none("Services", definition, alt_value={})
        self.set_services_targets(settings)
        self.set_services_scaling(settings)

    def debug_families_targets(self):
        """
        Method to troubleshoot family and service mapping
        """
        for family in self.families_targets:
            LOG.debug(f"Mapped {family[0].name} to {self.name}.")
            if not family[1] and family[2]:
                LOG.debug(f"Applies to service {family[2]}")
            else:
                LOG.debug(f"Applies to all services of {family[0].name}")

    @staticmethod
    def define_service_to_associate(
        service_name: str, family_name: str, settings: ComposeXSettings
    ) -> ComposeService:
        for _f_service in settings.families[family_name].services:
            if _f_service.name == service_name:
                _associated_service = _f_service
                break
        else:
            raise AttributeError(
                "Family {} does not have a service named {}: {}".format(
                    family_name,
                    service_name,
                    [svc.name for svc in settings.families[family_name].services],
                )
            )
        return _associated_service

    def handle_families_targets_expansion_dict(
        self, service_name: str, service_def: dict, settings: ComposeXSettings
    ) -> None:
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource
        """
        for svc in settings.services:
            if svc.name == service_name:
                the_service = svc
                break
        else:
            raise KeyError(
                f"Service {service_name} not found in ",
                [_svc.name for _svc in settings.services],
            )
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
                        set_else_none("Access", service_def, {}),
                        service_def,
                    )
                )

    def set_services_targets_from_dict(self, settings: ComposeXSettings) -> None:
        """
        Deals with services set as a dict
        """
        for service_name, service_def in self.services.items():
            if service_name in settings.family_names and service_name not in [
                tgt[0].name for tgt in self.families_targets
            ]:
                for family in settings.families.values():
                    if family.name == service_name:
                        break
                else:
                    raise ValueError("Failed to map service_name to families")
                self.families_targets.append(
                    (
                        family,
                        True,
                        family.services,
                        set_else_none("Access", service_def, {}),
                        service_def,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.debug(
                    f"{self.module.res_key}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in settings.service_names:
                self.handle_families_targets_expansion_dict(
                    service_name, service_def, settings
                )

    def set_services_targets(self, settings: ComposeXSettings) -> None:
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)
        """
        if not self.services:
            LOG.debug(f"{self.module.res_key}.{self.name} No Services defined.")
            return
        if not isinstance(self.services, dict):
            raise TypeError(
                "Services as list have been deprecated since version 1.0"
                "You can use the upgrade_scripts to patch your existing compose files."
            )
        self.set_services_targets_from_dict(settings)
        self.debug_families_targets()

    def handle_families_scaling_expansion_dict(
        self, service_name: str, service: dict, settings: ComposeXSettings
    ) -> None:
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource
        """
        the_service = [s for s in settings.services if s.name == service_name][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_scaling]:
                self.families_scaling.append(
                    (
                        settings.families[family_name],
                        service["Scaling"],
                    )
                )

    def set_services_targets_scaling_from_dict(
        self, settings: ComposeXSettings
    ) -> None:
        """Sets scaling targets to the resource for the defined services in the compose file."""
        for service_name, service_def in self.services.items():
            if not keyisset("Scaling", service_def):
                LOG.debug(
                    f"{self.module.res_key}.{self.name} - No Scaling set for {service_name}"
                )
                continue
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_scaling
            ]:
                self.families_scaling.append(
                    (
                        settings.families[service_name],
                        service_def["Scaling"],
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_scaling
            ]:
                LOG.debug(
                    f"{self.module.res_key}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_scaling_expansion_dict(
                    service_name, service_def, settings
                )

    def set_services_scaling(self, settings: ComposeXSettings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)
        """
        if not self.services:
            LOG.debug(f"{self.module.res_key}.{self.name} No Services defined.")
            return
        if not isinstance(self.services, dict):
            raise TypeError(
                "Services scaling must be in a mapping/dict format."
                "List format has been deprecated since 1.0"
            )
        self.set_services_targets_scaling_from_dict(settings)
