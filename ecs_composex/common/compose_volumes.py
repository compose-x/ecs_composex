#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Class and functions to interact with the volumes: defined in compose files.
"""

import re
from copy import deepcopy

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, Ref

from ecs_composex.common import LOG
from ecs_composex.efs.efs_params import FS_REGEXP, RES_KEY


def match_volumes_services_config(service, vol_config, volumes):
    """
    Function to map volume config in services and top-level volumes

    :param service:
    :param vol_config:
    :param volumes:
    :raises LookupError:
    """
    for volume in volumes:
        if volume.name == vol_config["source"]:
            volume.services.append(service)
            vol_config["volume"] = volume
            service.volumes.append(vol_config)
            LOG.info(f"Mapped {volume.name} to {service.name}")
            return
    raise LookupError(
        f"Volume {vol_config['source']} was not found in {[vol.name for vol in volumes]}"
    )


def handle_volume_str_config(service, config, volumes):
    """
    Function to return the volume configuration (long)
    :param ComposeService service:
    :param str config:
    :param list volumes:
    """
    volume_config = {"read_only": False}
    path_finder = re.compile(r"(^/[^:]+$)|(^[^:]+)(?::(/[\d\w/]+))(?::(ro$|rw$))?")
    path_match = path_finder.match(config)
    if not path_match:
        raise ValueError(
            f"Volume syntax {config} is invalid. Must follow the pattern",
            path_finder.pattern,
        )
    if path_match.groups()[0]:
        volume_config["source"] = path_match.groups()[0].strip("/").replace(r"/", "")
        volume_config["target"] = path_match.groups()[0]
        volume = ComposeVolume(
            volume_config["source"], {"type": "volume", "driver": "local"}
        )
        volumes.append(volume)
        LOG.info(f"Added self generated volume from path {volume_config['target']}")
    elif path_match.groups()[1] and path_match.groups()[2]:
        volume_config["source"] = path_match.groups()[1]
        volume_config["target"] = path_match.groups()[2]
        if path_match.groups()[3] and path_match.groups()[3] == "ro":
            volume_config["read_only"] = True
    match_volumes_services_config(service, volume_config, volumes)


def is_tmpfs(config):
    """
    Function to identify whether the volume defined is tmpfs

    :param dict config:
    :return: whether the volume defined is tmpfs
    :rtype: bool
    """
    if keyisset("tmpfs", config) or (
        keyisset("type", config) and config["type"] == "tmpfs"
    ):
        return True
    return False


def handle_volume_dict_config(service, config, volumes):
    """
    :param ComposeService service:
    :param dict config:
    :param list volumes:
    """
    volume_config = {"read_only": False}
    required_keys = ["target", "source"]
    if not is_tmpfs(config) and not all(key in config.keys() for key in required_keys):
        raise KeyError(
            "Volume configuration, when not tmpfs, requires at least",
            required_keys,
            "Got",
            config.keys(),
        )
    volume_config.update(config)
    if not is_tmpfs(volume_config):
        match_volumes_services_config(service, volume_config, volumes)


def evaluate_plugin_efs_properties(definition):
    """
    Function to parse the definition in case user uses the docker cli definition for EFS

    :return:
    """
    efs_keys = {
        "performance_mode": ("PerformanceMode", str),
        "throughput_mode": ("ThroughputMode", str),
        "provisioned_throughput": ("ProvisionedThroughputInMibps", (int, float)),
    }
    props = {}
    if keyisset(ComposeVolume.driver_opts_key, definition) and isinstance(
        definition[ComposeVolume.driver_opts_key], dict
    ):
        opts = definition[ComposeVolume.driver_opts_key]
        if keyisset("lifecycle_policy", opts) and isinstance(
            opts["lifecycle_policy"], str
        ):
            props["LifecyclePolicies"] = [{"TransitionToIA": opts["lifecycle_policy"]}]
        if keyisset("backup_policy", opts) and isinstance(opts["backup_policy"], str):
            props["BackupPolicy"] = {"Status": opts["backup_policy"]}
        for name, config in efs_keys.items():
            if not keyisset(name, opts):
                props[config[0]] = Ref(AWS_NO_VALUE)
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


class ComposeVolume(object):
    """
    Class to keep track of the Docker-compose Volumes

    When properties are defined, the priority in evaluation goes
    * x-efs
    * driver
    * driver_opts

    Assumed local when none else defined.
    """

    main_key = "volumes"
    driver_key = "driver"
    driver_opts_key = "driver_opts"
    efs_defaults = {
        "Encrypted": True,
        "LifecyclePolicies": [{"TransitionToIA": "AFTER_14_DAYS"}],
        "PerformanceMode": "generalPurpose",
    }

    def __init__(self, name, definition):
        self.name = name
        self.volume_name = name
        self.definition = deepcopy(definition)
        self.is_shared = False
        self.services = []
        self.parameters = {}
        self.device = None
        self.cfn_volume = None
        self.efs_definition = {}
        self.use = {}
        self.lookup = {}
        self.type = "volume"
        self.driver = "local"
        self.external = False
        self.efs_definition = evaluate_plugin_efs_properties(self.definition)
        if self.efs_definition:
            LOG.info("Identified properties as defined by Docker Plugin")
            self.type = "bind"
            self.driver = "nfs"
        elif (
            keyisset("external", self.definition)
            and keyisset("name", self.definition)
            and FS_REGEXP.match(self.definition["name"])
        ):
            LOG.warning("Identified a EFS to use")
            self.efs_definition = {"Use": self.definition["name"]}
            self.use = self.definition["name"]
        else:
            if keyisset(RES_KEY, self.definition):
                self.driver = "nfs"
                self.type = "bind"
                self.is_shared = True
                if keyisset("Lookup", self.efs_definition):
                    self.lookup = self.efs_definition["Lookup"]
                elif keyisset("Use", self.efs_definition):
                    self.use = self.efs_definition["Use"]
                if not self.use and not self.lookup:
                    self.efs_definition = (
                        self.definition[RES_KEY]["Properties"]
                        if keyisset("Properties", self.efs_definition)
                        else self.efs_defaults
                    )
                    self.parameters = (
                        self.definition[RES_KEY]["MacroParameters"]
                        if keyisset("MacroParameters", self.definition[RES_KEY])
                        else {}
                    )
            elif (
                not keyisset(RES_KEY, self.definition)
                and keyisset(self.driver_key, self.definition)
                and not keyisset(self.driver_opts_key, self.definition)
            ):
                if self.definition[self.driver_key] == "local":
                    self.type = "volume"
                    self.driver = "local"
                    self.efs_definition = None
                elif (
                    self.definition[self.driver_key] == "nfs"
                    or self.definition[self.driver_key] == "efs"
                ):
                    self.type = "bind"
                    self.is_shared = True
                    self.driver = "nfs"
            else:
                self.type = "volume"
                self.driver = "local"
                self.is_shared = False

    def __repr__(self):
        return self.name
