#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.logging import LOG
from ecs_composex.ecs.ecs_params import RUNTIME_CPU_ARCHITECTURE_T, RUNTIME_OS_FAMILY_T


def define_family_runtime_cpu_arch(family, svc) -> None:
    """
    Sets the CPU Runtime architecture set from services, if set.
    Validates that if set, it is the same for all

    :raises: ValueError
    """
    if svc.runtime_architecture and not family.runtime_cpu_arch:
        family.runtime_cpu_arch = svc.runtime_architecture
    elif (
        svc.runtime_architecture
        and family.runtime_cpu_arch
        and family.runtime_cpu_arch != svc.runtime_architecture
    ):
        raise ValueError(
            family.name,
            "You cannot have multiple containers in the same family run on different CPU architecture",
            [
                svc.runtime_architecture
                for svc in family.services
                if svc.runtime_architecture
            ],
        )


def define_family_runtime_os_family(family, svc) -> None:
    """
    Sets the Runtime Host OS Family set from services, if set.
    Validates that if set, it is the same for all

    :raises: ValueError
    """
    if svc.runtime_os_family and not family.runtime_os_family:
        family.runtime_os_family = svc.runtime_os_family
    elif (
        svc.runtime_os_family
        and family.runtime_os_family
        and family.runtime_os_family != svc.runtime_os_family
    ):
        raise ValueError(
            family.name,
            "You cannot have multiple containers in the same family run on different OS Hosts Family",
            [svc.runtime_os_family for svc in family.services if svc.runtime_os_family],
        )


def define_family_runtime_parameters(family) -> None:
    """
    Based on the services x-ecs. Configuration, allows to change the TaskDefinition Runtime configuration
    """
    for svc in family.ordered_services:
        define_family_runtime_cpu_arch(family, svc)
        define_family_runtime_os_family(family, svc)

    if family.stack and family.runtime_cpu_arch:
        family.stack.Parameters.update(
            {RUNTIME_CPU_ARCHITECTURE_T: family.runtime_cpu_arch}
        )
        LOG.info(
            f"{family.name} - Host CPU Architecture updated to {family.runtime_cpu_arch}"
        )
    if family.stack and family.runtime_os_family:
        family.stack.Parameters.update({RUNTIME_OS_FAMILY_T: family.runtime_os_family})
        LOG.info(
            f"{family.name} - OS Host Family updated to {family.runtime_os_family}"
        )
