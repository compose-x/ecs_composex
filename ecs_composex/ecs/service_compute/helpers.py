#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keypresent, set_else_none
from troposphere.ecs import CapacityProviderStrategyItem

from ecs_composex.common.logging import LOG


def merge_capacity_providers(service_compute):
    """
    Merge capacity providers set on the services of the task service_compute.family if service is not sidecar
    """
    task_config = {}
    for svc in service_compute.family.ordered_services:
        if not svc.capacity_provider_strategy or svc.is_aws_sidecar:
            continue
        for provider in svc.capacity_provider_strategy:
            if provider["CapacityProvider"] not in task_config.keys():
                name = provider["CapacityProvider"]
                task_config[name] = {
                    "Base": [],
                    "Weight": [],
                    "CapacityProvider": name,
                }
                task_config[name]["Base"].append(
                    set_else_none("Base", provider, alt_value=0)
                )
                task_config[name]["Weight"].append(
                    set_else_none("Weight", provider, alt_value=0)
                )
    for count, provider in enumerate(task_config.values()):
        if count == 0:
            provider["Base"] = int(max(provider["Base"]))
        elif count > 0 and keypresent("Base", provider):
            del provider["Base"]
            LOG.warning(
                f"{service_compute.family.name}.x-ecs Only one capacity provider can have a base value. "
                f"Deleting Base for {provider['CapacityProvider']}"
            )
        provider["Weight"] = int(max(provider["Weight"]))
    service_compute.ecs_capacity_providers = [
        CapacityProviderStrategyItem(**config) for config in task_config.values()
    ]
