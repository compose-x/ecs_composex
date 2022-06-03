#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import If, NoValue
from troposphere.ecs import KernelCapabilities

from ecs_composex.ecs.ecs_conditions import USE_FARGATE_CON_T


def set_add_capacities(service, add_key, valid, cap_adds, all_adds, fargate):
    """
    Method to set the kernel capacities to add

    :param str add_key:
    :param list valid:
    :param list cap_adds:
    :param list all_adds:
    :param list fargate:
    """
    to_add = set_else_none(add_key, service.definition, alt_value=[])

    for capacity in to_add:
        if capacity not in valid:
            raise ValueError(
                f"Linux kernel capacity {capacity} is not supported in ECS or simply not valid"
            )
        if capacity in fargate:
            cap_adds.append(capacity)
        else:
            all_adds.append(capacity)


def set_drop_capacities(
    service, drop_key, valid, cap_adds, all_adds, all_drops, fargate
):
    """
    Set the drop kernel capacities

    :param str drop_key:
    :param list valid:
    :param list cap_adds:
    :param list all_adds:
    :param list all_drops:
    :param list fargate:
    """
    to_drop = set_else_none(drop_key, service.definition, alt_value=[])
    for capacity in to_drop:
        if capacity not in valid:
            raise ValueError(
                f"{service.name} - Linux kernel capacity {capacity} is not supported in ECS or simply not valid"
            )
        if capacity in all_adds or capacity in cap_adds:
            raise KeyError(
                f"{service.name} - Capacity {capacity} already detected in cap_add. "
                "You cannot both add and remove the capacity"
            )
        if capacity in fargate:
            cap_adds.append(capacity)
        else:
            all_drops.append(capacity)


def define_kernel_options(service):
    """
    Define and return the kernel option settings for cap_add and cap_drop
    """
    valid = [
        "ALL",
        "AUDIT_CONTROL",
        "AUDIT_WRITE",
        "BLOCK_SUSPEND",
        "CHOWN",
        "DAC_OVERRIDE",
        "DAC_READ_SEARCH",
        "FOWNER",
        "FSETID",
        "IPC_LOCK",
        "IPC_OWNER",
        "KILL",
        "LEASE",
        "LINUX_IMMUTABLE",
        "MAC_ADMIN",
        "MAC_OVERRIDE",
        "MKNOD",
        "NET_ADMIN",
        "NET_BIND_SERVICE",
        "NET_BROADCAST",
        "NET_RAW",
        "SETFCAP",
        "SETGID",
        "SETPCAP",
        "SETUID",
        "SYS_ADMIN",
        "SYS_BOOT",
        "SYS_CHROOT",
        "SYS_MODULE",
        "SYS_NICE",
        "SYS_PACCT",
        "SYS_PTRACE",
        "SYS_RAWIO",
        "SYS_RESOURCE",
        "SYS_TIME",
        "SYS_TTY_CONFIG",
        "SYSLOG",
        "WAKE_ALARM",
    ]
    fargate = ["SYS_PTRACE"]
    add_key = "cap_add"
    drop_key = "cap_drop"
    cap_adds = []
    cap_drops = []
    all_adds = []
    all_drops = []
    if not keyisset(add_key, service.definition) and not keyisset(
        drop_key, service.definition
    ):
        return NoValue

    set_add_capacities(service, add_key, valid, cap_adds, all_adds, fargate)
    set_drop_capacities(
        service, drop_key, valid, cap_adds, all_adds, all_drops, fargate
    )
    kwargs = {
        "Add": cap_adds or NoValue,
        "Drop": cap_drops or NoValue,
    }
    if all_adds:
        cap_adds.append(If(USE_FARGATE_CON_T, NoValue, all_adds))
    if all_drops:
        cap_drops.append(If(USE_FARGATE_CON_T, NoValue, all_drops))
    return KernelCapabilities(**kwargs)
