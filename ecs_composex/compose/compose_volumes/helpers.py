#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
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
    if keyisset(driver_opts_key, definition) and isinstance(
        definition[driver_opts_key], dict
    ):
        opts = definition[driver_opts_key]
        if keyisset("lifecycle_policy", opts) and isinstance(
            opts["lifecycle_policy"], str
        ):
            props["LifecyclePolicies"] = [{"TransitionToIA": opts["lifecycle_policy"]}]
        if keyisset("backup_policy", opts) and isinstance(opts["backup_policy"], str):
            props["BackupPolicy"] = {"Status": opts["backup_policy"]}
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
