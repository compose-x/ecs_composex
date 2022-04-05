#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere import NoValue

from ecs_composex.ecs.ecs_params import LAUNCH_TYPE
from ecs_composex.ecs_cluster import FARGATE_PROVIDERS
from ecs_composex.ecs_composex import LOG

"""
Module to set the Launch Type / Capacity providers of ComposeFamily according to the ECS Cluter settings
and x-ecs settings
"""


def validate_capacity_providers(family, cluster):
    """
    Validates that the defined ecs_capacity_providers are all available in the ECS Cluster Providers

    :param family:
    :param cluster: The cluster object
    :raises: ValueError if not all task family providers in the cluster providers
    :raises: TypeError if cluster_providers not a list
    """
    if (
        not family.service_compute.ecs_capacity_providers
        and not cluster.capacity_providers
    ):
        LOG.debug(
            f"{family.name} - No capacity providers specified in task definition nor cluster"
        )
        return True
    elif not cluster.capacity_providers:
        LOG.debug(f"{family.name} - No capacity provider set for cluster")
        return True
    cap_names = [
        cap.CapacityProvider for cap in family.service_compute.ecs_capacity_providers
    ]
    if not all(cap_name in FARGATE_PROVIDERS for cap_name in cap_names):
        raise ValueError(
            f"{family.name} - You cannot mix FARGATE capacity provider with AutoScaling Capacity Providers",
            cap_names,
        )
    if not isinstance(cluster.capacity_providers, list):
        raise TypeError("clusters_providers must be a list")

    elif not all(provider in cluster.capacity_providers for provider in cap_names):
        raise ValueError(
            "Providers",
            cap_names,
            "not defined in ECS Cluster providers. Valid values are",
            cluster.capacity_providers,
        )


def validate_compute_configuration_for_task(family, settings):
    """
    Function to perform a final validation of compute before rendering.

    :param family:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if (
        family.service_compute.launch_type
        and family.service_compute.launch_type == "EXTERNAL"
    ):
        LOG.debug(f"{family.name} - Launch Type set to EXTERNAL. Nothing to do.")
        return
    if settings.ecs_cluster.platform_override:
        family.service_compute.launch_type = settings.ecs_cluster.platform_override
        LOG.warning(
            f"{family.name} - Due to Launch Type override to {settings.ecs_cluster.platform_override}"
            ", ignoring CapacityProviders"
            f"{[_cap.CapacityProvider for _cap in family.service_compute.ecs_capacity_providers]}"
        )
        if family.ecs_service.ecs_service:
            setattr(
                family.service_definition,
                "CapacityProviderStrategy",
                NoValue,
            )
    else:
        family.service_compute.set_update_launch_type()
        family.service_compute.set_update_capacity_providers()
        validate_capacity_providers(family, settings.ecs_cluster)
        if family.service_compute.launch_type in ["EC2", "EXTERNAL", "FARGATE"]:
            return
        set_service_launch_type(family, settings.ecs_cluster)
        LOG.debug(
            f"{family.name} - Updated {LAUNCH_TYPE.title} to"
            f" {family.service_compute.launch_type}"
        )


def set_launch_type_from_cluster_and_service(family):
    if all(
        provider.CapacityProvider in ["FARGATE", "FARGATE_SPOT"]
        for provider in family.service_compute.ecs_capacity_providers
    ):
        LOG.debug(
            f"{family.name} - Cluster and Service use Fargate only. Setting to FARGATE_PROVIDERS"
        )
        family.service_compute.launch_type = "FARGATE_PROVIDERS"
    else:
        family.service_compute.launch_type = "SERVICE_MODE"
        LOG.info(
            f"{family.name} - Using AutoScaling Based Providers",
            [
                provider.CapacityProvider
                for provider in family.service_compute.ecs_capacity_providers
            ],
        )


def set_launch_type_from_cluster_only(family, cluster):
    if any(
        provider in ["FARGATE", "FARGATE_SPOT"]
        for provider in cluster.default_strategy_providers
    ) or all(
        provider in cluster.capacity_providers
        for provider in ["FARGATE", "FARGATE_SPOT"]
    ):
        family.service_compute.launch_type = "FARGATE_PROVIDERS"
        LOG.debug(
            f"{family.name} - Defaulting to FARGATE_PROVIDERS as "
            "FARGATE[_SPOT] is found in the cluster default strategy"
        )
    else:
        family.service_compute.launch_type = "CLUSTER_MODE"
        LOG.debug(
            f"{family.name} - Cluster uses non Fargate Capacity Providers. Setting to Cluster default"
        )
        family.service_compute.launch_type = "CLUSTER_MODE"


def set_service_launch_type(family, cluster):
    """
    Sets the LaunchType value for the ECS Service
    """
    if (
        family.service_compute.launch_type == "EXTERNAL"
        or family.service_compute.launch_type == "EC2"
    ):
        return
    if family.service_compute.ecs_capacity_providers and cluster.capacity_providers:
        set_launch_type_from_cluster_and_service(family)
    elif (
        not family.service_compute.ecs_capacity_providers and cluster.capacity_providers
    ):
        set_launch_type_from_cluster_only(family, cluster)
