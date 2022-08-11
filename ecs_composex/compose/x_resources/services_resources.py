#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.compose_x_common import keyisset, set_else_none

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.compose.x_resources import XResource
from ecs_composex.compose.x_resources.helpers import get_setting_key


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
        self.families_targets = []
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

    def handle_families_targets_expansion(self, service, settings):
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        """
        name_key = get_setting_key("name", service)
        access_key = get_setting_key("access", service)
        the_service = [s for s in settings.services if s.name == service[name_key]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [the_service],
                        service[access_key],
                        service,
                    )
                )

    def set_services_targets_from_list(self, settings):
        """
        Deals with services set as a list
        """
        for service in self.services:
            name_key = get_setting_key("name", service)
            access_key = get_setting_key("access", service)
            service_name = service[name_key]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service[access_key],
                        service,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.debug(
                    f"{self.module.res_key}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion(service, settings)

    def handle_families_targets_expansion_dict(
        self, service_name, service, settings
    ) -> None:
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param str service_name:
        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
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
                        [the_service],
                        service["Access"] if keyisset("Access", service) else {},
                        service,
                    )
                )

    def set_services_targets_from_dict(self, settings):
        """
        Deals with services set as a dict
        """
        for service_name, service_def in self.services.items():
            if service_name in [
                family.name for family in settings.families.values()
            ] and service_name not in [tgt[0].name for tgt in self.families_targets]:
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
                        service_def["Access"]
                        if keyisset("Access", service_def)
                        else {},
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

    def set_services_targets(self, settings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            LOG.debug(f"{self.module.res_key}.{self.name} No Services defined.")
            return
        if isinstance(self.services, list):
            self.set_services_targets_from_list(settings)
        elif isinstance(self.services, dict):
            self.set_services_targets_from_dict(settings)
        self.debug_families_targets()

    def handle_family_scaling_expansion(self, service, settings):
        """
        Method to search for the families of given service and add it if not already present

        :param dict service:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        name_key = get_setting_key("name", service)
        scaling_key = get_setting_key("scaling", service)
        the_service = [s for s in settings.services if s.name == service[name_key]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_scaling]:
                self.families_scaling.append(
                    (settings.families[family_name], service[scaling_key])
                )

    def set_services_scaling_list(self, settings):
        """
        Method to map services and families targets of the services defined.

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services or isinstance(self.services, dict):
            return
        for service in self.services:
            name_key = get_setting_key("name", service)
            scaling_key = get_setting_key("scaling", service)
            if not keyisset(scaling_key, service):
                LOG.debug(
                    f"{self.module.res_key}.{self.name} - No Scaling set for {service[name_key]}"
                )
                continue
            service_name = service[name_key]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_scaling
            ]:
                self.families_scaling.append(
                    (settings.families[service_name], service[scaling_key])
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_scaling
            ]:
                LOG.debug(
                    f"{self.module.res_key}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_family_scaling_expansion(service, settings)

    def handle_families_scaling_expansion_dict(self, service_name, service, settings):
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param str service_name:
        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
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

    def set_services_targets_scaling_from_dict(self, settings) -> None:
        """
        Deals with services set as a dict

        :param settings:
        """
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

    def set_services_scaling(self, settings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            LOG.debug(f"{self.module.res_key}.{self.name} No Services defined.")
            return
        if isinstance(self.services, list):
            self.set_services_scaling_list(settings)
        elif isinstance(self.services, dict):
            self.set_services_targets_scaling_from_dict(settings)
