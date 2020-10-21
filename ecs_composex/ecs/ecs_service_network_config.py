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
                if config[1] is bool and keypresent(config[0], network):
                    network_config[config[0]] = network[config[0]]
                elif config[1] is str and keyisset(config[0], network):
                    network_config[config[0]] = network[config[0]]
                elif config[1] is dict and keypresent(config[0], network) and config[2]:
                    config[2](network_config[config[0]], network[config[0]])
    LOG.debug(family.name)
    LOG.debug(dumps(network_config, indent=2))
    return network_config


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
