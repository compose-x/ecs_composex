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
Module to help with defining the network settings for the ECS Service based on the family services definitions.
"""

from json import dumps

from ecs_composex.common import keyisset, keypresent
from ecs_composex.common import LOG


def handle_ext_sources(existing_sources, new_sources):
    LOG.debug("Source", dumps(existing_sources, indent=2))
    set_ipv4_sources = [s["ipv4"] for s in existing_sources if keyisset("ipv4", s)]
    for new_s in new_sources:
        if new_s not in set_ipv4_sources:
            existing_sources.append(new_s)


def handle_aws_sources(existing_sources, new_sources):
    LOG.debug("Source", dumps(existing_sources, indent=2))
    set_ids = [s["id"] for s in existing_sources if keyisset("id", s)]
    allowed_keys = ["PrefixList", "SecurityGroup"]
    for new_s in new_sources:
        if new_s not in set_ids and new_s["type"] in allowed_keys:
            existing_sources.append(new_s)
        elif new_s["id"] not in allowed_keys:
            LOG.error(
                f"AWS Source type incorrect: {new_s['type']}. Expected one of {allowed_keys}"
            )


def handle_ingress_rules(source_config, ingress_config):
    LOG.debug("Source", dumps(source_config, indent=2))
    valid_keys = [
        ("myself", bool, None),
        ("ext_sources", list, handle_ext_sources),
        ("aws_sources", list, handle_aws_sources),
    ]
    for key in valid_keys:
        if keypresent(key[0], ingress_config) and isinstance(
            ingress_config[key[0]], key[1]
        ):
            if key[1] is bool and not keyisset(key[0], source_config):
                source_config[key[0]] = ingress_config[key[0]]
            if (
                key[1] is bool
                and keyisset(key[0], source_config)
                and not keyisset(key[0], ingress_config)
            ):
                LOG.warn(
                    "At least one service in the task requires access to itself. Skipping."
                )
            elif key[1] is list and keyisset(key[0], ingress_config) and key[2]:
                key[2](source_config[key[0]], ingress_config[key[0]])


def handle_merge_services_props(config, network, network_config):
    """
    Function to handle properties assignment for network settings

    :param tuple config:
    :param dict network:
    :param dict network_config:
    :return:
    """
    if config[1] is bool and keypresent(config[0], network):
        network_config[config[0]] = network[config[0]]
    elif config[1] is str and keyisset(config[0], network):
        network_config[config[0]] = network[config[0]]
    elif config[1] is dict and keypresent(config[0], network) and config[2]:
        config[2](network_config[config[0]], network[config[0]])


def merge_services_network(family):
    network_config = {
        "use_cloudmap": True,
        "ingress": {"myself": False, "ext_sources": [], "aws_sources": []},
        "is_public": False,
        "lb_type": None,
    }
    valid_keys = [
        ("ingress", dict, handle_ingress_rules),
        ("use_cloudmap", bool, None),
        ("is_public", bool, None),
        ("lb_type", str, None),
    ]
    x_network = [
        s.x_configs["network"]
        for s in family.ordered_services
        if s.x_configs and keyisset("network", s.x_configs)
    ]
    for config in valid_keys:
        for network in x_network:
            if config[0] in network:
                handle_merge_services_props(config, network, network_config)
    LOG.debug(family.name)
    LOG.debug(dumps(network_config, indent=2))
    return network_config


def define_protocol(port_string):
    """
    Function to define the port protocol. Defaults to TCP if not specified otherwise

    :param port_string: the port string to parse from the ports list in the compose file
    :type port_string: str
    :return: protocol, ie. udp or tcp
    :rtype: str
    """
    protocols = ["tcp", "udp"]
    protocol = "tcp"
    if port_string.find("/"):
        protocol_found = port_string.split("/")[-1].strip()
        if protocol_found in protocols:
            return protocol_found
    return protocol


def set_service_ports(ports):
    """Function to define common structure to ports

    :return: list of ports the ecs_service uses formatted according to dict
    :rtype: list
    """
    service_ports = []
    for port in ports:
        if not isinstance(port, (str, dict, int)):
            raise TypeError(
                "ports must be of types", dict, "or", list, "got", type(port)
            )
        if isinstance(port, str):
            service_ports.append(
                {
                    "protocol": define_protocol(port),
                    "published": int(port.split(":")[0]),
                    "target": int(port.split(":")[-1].split("/")[0].strip()),
                    "mode": "awsvpc",
                }
            )
        elif isinstance(port, dict):
            valid_keys = ["published", "target", "protocol", "mode"]
            if not set(port).issubset(valid_keys):
                raise KeyError("Valid keys are", valid_keys, "got", port.keys())
            port["mode"] = "awsvpc"
            service_ports.append(port)
        elif isinstance(port, int):
            service_ports.append(
                {
                    "protocol": "tcp",
                    "published": port,
                    "target": port,
                    "mode": "awsvpc",
                }
            )
    LOG.debug(service_ports)
    return service_ports


class ServiceNetworking(object):
    """
    Class to group the configuration for Service network settings
    """

    defined = True
    network_settings = ["ingress", "use_cloudmap", "is_public", "lb_type"]

    def __init__(self, family):
        self.configuration = merge_services_network(family)
        self.lb_type = self.configuration["lb_type"]
        self.is_public = self.configuration["is_public"]
        self.aws_sources = []
        self.ext_sources = []
        self.ingress_from_self = True
        if keyisset("ingress", self.configuration):
            self.ext_sources = self.configuration["ingress"]["ext_sources"]
            self.aws_sources = self.configuration["ingress"]["aws_sources"]
            self.ingress_from_self = self.configuration["ingress"]["myself"]
        self.ports = []
        self.merge_services_ports(family)

    def __repr__(self):
        return dumps(self.configuration, indent=2)

    def use_nlb(self):
        """
        Method to indicate if the current lb_type is network

        :return: True or False
        :rtype: bool
        """
        if self.lb_type == "network":
            return True
        return False

    def use_alb(self):
        """
        Method to indicate if the current lb_type is application

        :return: True or False
        :rtype: bool
        """
        if self.lb_type == "application":
            return True
        return False

    def merge_services_ports(self, family):
        """
        Function to merge two sections of ports

        :param ecs_composex.common.compose_services.ComposeFamily family:
        :return:
        """
        source_ports = [
            service.ports for service in family.ordered_services if service.ports
        ]
        for port_set in source_ports:
            f_source_ports = set_service_ports(self.ports)
            f_override_ports = set_service_ports(port_set)
            self.ports = []
            f_overide_ports_targets = [port["target"] for port in f_override_ports]
            for port in f_override_ports:
                self.ports.append(port)
                for s_port in f_source_ports:
                    if s_port["target"] not in f_overide_ports_targets:
                        self.ports.append(s_port)
