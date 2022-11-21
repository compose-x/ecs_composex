#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule, ModManager


from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG
from ecs_composex.compose.x_resources.services_resources import ServicesXResource
from ecs_composex.rds_resources_settings import handle_new_tcp_resource, import_dbs
from ecs_composex.resource_settings import link_resource_to_services


class NetworkXResource(ServicesXResource):

    """
    Class for resources that need VPC and SecurityGroups to be managed for Ingress
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        self.subnets_override = None
        self.security_group = None
        self.security_group_param = None
        self.port_param = None
        super().__init__(name, definition, module, settings)
        self.requires_vpc = True
        self.cleanse_external_targets()
        self.set_override_subnets()
        self.cloudmap_dns_supported = True

    def remove_services_after_family_cleanups(self) -> None:
        """
        After the family services have been removed from the target, we ensure that we deal with the services
        which may or may not be in the targets already
        """
        if isinstance(self.services, list):
            for service in self.services:
                family_name = (
                    service["name"].split(":")[0]
                    if r":" in service["name"]
                    else service["name"]
                )
                for family in self.families_targets:
                    if family[0].name == family_name or family_name in [
                        svc.name for svc in family[0].services
                    ]:
                        break
                else:
                    self.services.remove(service)

        elif isinstance(self.services, dict):
            to_del = []
            for service_name, service in self.services.items():
                family_name = (
                    service_name.split(":")[0] if r":" in service_name else service_name
                )
                for family in self.families_targets:
                    if family[0].name == family_name or family_name in [
                        svc.name for svc in family[0].services
                    ]:
                        break
                else:
                    to_del.append(service_name)
            for key in to_del:
                print(f"{self.module.res_key}.{self.name} - Removing service {key}")
                del self.services[key]

    def cleanse_external_targets(self) -> None:
        """
        Will automatically remove the target families which are set as external
        """
        for target in self.families_targets:
            if (
                target[0].service_compute
                and target[0].service_compute.launch_type == "EXTERNAL"
            ):
                LOG.info(
                    f"{self.module.res_key}.{self.name} - Target {target[0].name} - "
                    "Launch Type not supported (EXTERNAL)"
                )
                self.families_targets.remove(target)
        for target in self.families_scaling:
            if (
                target[0].service_compute
                and target[0].service_compute.launch_type == "EXTERNAL"
            ):
                LOG.info(
                    f"{self.module.res_key}.{self.name} - Target {target[0].name} "
                    "- Launch Type not supported (EXTERNAL)"
                )
                self.families_scaling.remove(target)
        self.remove_services_after_family_cleanups()

    def set_override_subnets(self) -> None:
        """
        Updates the subnets to use from default for the given resource
        """
        if (
            self.settings
            and keyisset("Subnets", self.settings)
            and hasattr(self, "subnets_param")
        ):
            self.subnets_override = self.settings["Subnets"]
        elif (
            self.parameters
            and keyisset("Subnets", self.parameters)
            and hasattr(self, "subnets_param")
        ):
            self.subnets_override = self.parameters["Subnets"]

    def update_from_vpc(self, vpc_stack, settings=None):
        """
        Allows to make adjustments after the VPC Settings have been set
        """
        pass


class DatabaseXResource(NetworkXResource):
    """
    Class for network resources that share common properties

    :ivar ecs_composex.common.cfn_params.Parameter db_secret_arn_parameter:
    :ivar ecs_composex.common.cfn_params.Parameter db_cluster_endpoint_param:
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        self.db_secret = None
        self.db_secret_arn_parameter = None
        self.db_cluster_arn_parameter = None
        self.db_cluster_arn = None
        self.db_cluster_endpoint_param = None
        self.db_cluster_ro_endpoint_param = None
        super().__init__(name, definition, module, settings)
        self.default_cloudmap_settings = {
            "DnsSettings": {
                "Hostname": self.logical_name,
            },
        }

    def to_ecs(self, settings, modules: ModManager, root_stack=None) -> None:
        """
        Maps a database service to ECS services

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ModManager modules:
        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        """
        if not self.mappings and self.cfn_resource:
            handle_new_tcp_resource(
                self,
                port_parameter=self.port_param,
                sg_parameter=self.security_group_param,
                secret_parameter=self.db_secret_arn_parameter,
                settings=settings,
            )
            if self.db_cluster_arn_parameter:
                link_resource_to_services(
                    settings,
                    self,
                    arn_parameter=self.db_cluster_arn_parameter,
                    access_subkeys=["DBCluster"],
                )
        elif self.mappings and not self.cfn_resource:
            import_dbs(self, settings)
