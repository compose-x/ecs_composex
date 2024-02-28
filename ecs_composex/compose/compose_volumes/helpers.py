#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import NoValue


def evaluate_plugin_efs_properties(definition, driver_opts_key):
    """
    Function to parse the definition in case user uses the docker cli definition for EFS

    :return:
    """
    efs_keys = {
        "performance_mode": ("PerformanceMode", str),
        "throughput_mode": ("ThroughputMode", str),
        "provisioned_throughput": (
            "ProvisionedThroughputInMibps",
            (int, float),
        ),
    }
    props = {}
    opts = set_else_none(driver_opts_key, definition, {})
    if not opts:
        return props
    lifecycle_policy = set_else_none("lifecycle_policy", opts)
    backup_policy = set_else_none("backup_policy", opts)
    if lifecycle_policy:
        props["LifecyclePolicies"] = [{"TransitionToIA": lifecycle_policy}]
    if backup_policy:
        props["BackupPolicy"] = {"Status": backup_policy}
    for name, config in efs_keys.items():
        if not keyisset(name, opts):
            props[config[0]] = NoValue
        elif not isinstance(opts[name], config[1]):
            raise TypeError(
                f"Property {name} is of type",
                type(opts[name]),
                "Expected",
                config[1],
            )
        else:
            props[config[0]] = opts[name]
    return props
