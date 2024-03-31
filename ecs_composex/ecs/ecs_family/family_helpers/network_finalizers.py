#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@compose-x.io>

"""Functions to finalize the family networking settings"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily

from troposphere import NoValue


def finalize_network_settings(
    family: ComposeFamily, settings: ComposeXSettings
) -> None:
    """
    Evaluates the ECS Connect settings to be configured by the service.
    If there is a configuration to be set, ensures it's set on the ECS Service definition.
    """
    family.service_networking.set_ecs_connect(settings)
    if family.service_networking.ecs_connect_config and family.ecs_service:
        setattr(
            family.ecs_service.ecs_service,
            "ServiceConnectConfiguration",
            family.service_networking.ecs_connect_config,
        )


def finalize_lb_settings(family: ComposeFamily) -> None:
    """
    Ensures that the LoadBalancers & ServiceRegistries (LB & CloudMap) are set appropriately based on
    the deployment settings. Especially, resets properties if the service is deployed to ECS Anywhere.
    Ensures correctness of LinuxParameters for each of the services.
    """
    if family.service_compute.launch_type == "EXTERNAL":
        if hasattr(family.service_definition, "LoadBalancers"):
            setattr(family.service_definition, "LoadBalancers", NoValue)
        if hasattr(family.service_definition, "ServiceRegistries"):
            setattr(family.service_definition, "ServiceRegistries", NoValue)
        for container in family.task_definition.ContainerDefinitions:
            if hasattr(container, "LinuxParameters"):
                parameters = getattr(container, "LinuxParameters")
                setattr(parameters, "InitProcessEnabled", False)
