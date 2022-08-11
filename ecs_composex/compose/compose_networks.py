#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Class and functions to interact with the networks: defined in compose files.
"""

from copy import deepcopy

from compose_x_common.compose_x_common import set_else_none

from ecs_composex.common.logging import LOG


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


class ComposeNetwork:
    """
    Class to keep track of the Docker-compose Volumes
    """

    main_key = "networks"
    driver_opts_key = "driver"

    def __init__(self, name, definition, subnets_list):
        self.name = name
        self.definition = deepcopy(definition)
        self.subnet_name = set_else_none("x-vpc", definition, None)
        subnet_names = [subnet.title for subnet in subnets_list]
        if self.subnet_name and self.subnet_name not in subnet_names:
            raise KeyError(
                f"networks.{name} - x-vpc.{self.subnet_name} defined. Valid options are",
                subnet_names,
            )
