#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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
Class and functions to interact with the networks: defined in compose files.
"""

from ecs_composex.common import keyisset, LOG


def match_networks_services_config(service, net_config, networks):
    """
    Function to map network config in services and top-level networks

    :param service:
    :param dict net_config:
    :param list networks:
    :raises LookupError:
    """
    for network in networks:
        if network.name == net_config["source"]:
            network.services.append(service)
            net_config["network"] = network
            service.networks.append(net_config)
            LOG.info(f"Mapped {network.name} to {service.name}")
            return
    raise LookupError(
        f"Volume {net_config['source']} was not found in {[vol.name for vol in networks]}"
    )


class ComposeNetwork(object):
    """
    Class to keep track of the Docker-compose Volumes
    """

    main_key = "networks"
    driver_opts_key = "driver"

    def __init__(self, name, definition, subnets_list):
        self.name = name
        self.subnet_name = name
        if keyisset("name", definition):
            self.subnet_name = definition["name"]
        elif (
            not keyisset("name", definition)
            and keyisset("x-vpc", definition)
            and isinstance(definition["x-vpc"], str)
        ):
            self.subnet_name = definition["x-vpc"]
        subnet_names = [subnet.title for subnet in subnets_list]
        if self.subnet_name not in subnet_names:
            raise KeyError(
                f"No subnet {self.name} defined. Valid options are", subnet_names
            )
