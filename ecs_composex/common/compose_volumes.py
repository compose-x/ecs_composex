#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Class and functions to interact with the volumes: defined in compose files.
"""

import re

from ecs_composex.common import keyisset, LOG


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
    path_pattern = r"(^[^:]+$)|(^[^:]+)(:\/[\d\w\/]+)(:ro$|:rw$)?"
    path_finder = re.compile(path_pattern)
    path_match = path_finder.match(config)
    if not path_match:
        raise ValueError(
            f"Volume syntax {config} is invalid. Must follow the pattern", path_pattern
        )
    if path_match.groups()[0]:
        volume_config["source"] = path_match.groups()[0]
        volume_config["target"] = f"/{path_match.groups()[0]}"
    elif path_match.groups()[1] and path_match.groups()[2]:
        volume_config["source"] = path_match.groups()[1]
        volume_config["target"] = path_match.groups()[2]
        if path_match.groups()[3] and path_match.groups()[3] == "ro":
            volume_config["read_only"] = True
    match_volumes_services_config(service, volume_config, volumes)


def handle_volume_dict_config(service, config, volumes):
    """
    :param ComposeService service:
    :param dict config:
    :param list volumes:
    """
    volume_config = {"read_only": False}
    required_keys = ["target", "source"]
    if not all(key in config.keys() for key in required_keys):
        raise KeyError(
            "Volume configuration requires at least",
            required_keys,
            "Got",
            config.keys(),
        )
    volume_config.update(config)
    match_volumes_services_config(service, volume_config, volumes)


class ComposeVolume(object):
    """
    Class to keep track of the Docker-compose Volumes
    """

    main_key = "volumes"
    driver_opts_key = "driver_opts"

    def __init__(self, name, definition):
        self.name = name
        self.volume_name = name
        self.efs_volume = (
            definition["x-efs"]
            if keyisset("x-efs", definition) and isinstance(definition["x-efs"], str)
            else None
        )
        self.services = []
        self.device = None
        self.cfn_fs = None
        self.cfn_ap = None
        self.type = "local" if not self.efs_volume else "nfs"

        if (
            keyisset(self.driver_opts_key, definition)
            and isinstance(definition[self.driver_opts_key], dict)
            and keyisset("type", definition[self.driver_opts_key])
            and isinstance(definition[self.driver_opts_key]["type"], str)
            and definition[self.driver_opts_key]["type"] == "nfs"
        ):
            self.type = "efs"
            if keyisset("device", definition[self.driver_opts_key]):
                self.root_folder = definition[self.driver_opts_key]["device"]
            if keyisset("o", definition[self.driver_opts_key]):
                self.mount_options_raw = definition[self.driver_opts_key]["o"]
