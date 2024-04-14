#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import Ref

from ecs_composex.common.logging import LOG


def update_family_subnets(family: ComposeFamily, settings: ComposeXSettings) -> None:
    """
    Update the stack parameters of the family stack AppSubnets Parameter value to the one matching with
    networks.x-vpc and networks.[]
    """
    network_names = list(family.service_networking.networks.keys())
    for network in settings.networks:
        if not network.subnet_name:
            continue
        if network.name in network_names:
            family.service_networking.subnets = Ref(network.subnet_name)
            LOG.info(
                f"networks.{network.name} - "
                f"mapped x-vpc.{network.subnet_name} to {family.name}"
            )
            break
    else:
        LOG.error(
            f"{family.name}.networks - unable to assign AppSubnets to a top-level defined network"
        )


def set_family_hostname(family: ComposeFamily):
    """
    Sets the hostname to use for the Family in Cloudmap.
    If it has been set on more than one service container, it uses the first one.
    """
    svcs_hostnames = any(svc.family_hostname for svc in family.services)
    if not svcs_hostnames or not family.family_hostname:
        LOG.debug(
            f"{family.name} - No ecs.task.family.hostname defined on any of the services. "
            f"Setting to {family.family_hostname}"
        )
        return
    potential_svcs = []
    for svc in family.services:
        if (
            svc.family_hostname
            and hasattr(svc, "container_definition")
            and svc.container_definition.Essential
        ):
            potential_svcs.append(svc)
    uniq = []
    for svc in potential_svcs:
        if svc.family_hostname not in uniq:
            uniq.append(svc.family_hostname)
    family.family_hostname = uniq[0].lower().replace("_", "-")
    if len(uniq) > 1:
        LOG.warning(
            f"{family.name} more than one essential container has ecs.task.family.hostname set. "
            f"Using the first one {uniq[0]}"
        )
