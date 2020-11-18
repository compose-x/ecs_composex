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

from troposphere import AWS_ACCOUNT_ID
from troposphere import Sub, Ref, GetAtt
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.ingress_settings import (
    flatten_ip,
    generate_security_group_props,
    set_service_ports,
    Ingress,
)
from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common import keyisset, keypresent
from ecs_composex.ecs.ecs_params import SERVICE_NAME_T


def handle_ext_sources(existing_sources, new_sources):
    LOG.debug("Source", dumps(existing_sources, indent=2))
    set_ipv4_sources = [
        s[Ingress.ipv4_key] for s in existing_sources if keyisset(Ingress.ipv4_key, s)
    ]
    for new_s in new_sources:
        if new_s not in set_ipv4_sources:
            existing_sources.append(new_s)


def handle_aws_sources(existing_sources, new_sources):
    LOG.debug("Source", dumps(existing_sources, indent=2))
    set_ids = [s["Id"] for s in existing_sources if keyisset("id", s)]
    allowed_keys = ["PrefixList", "SecurityGroup"]
    for new_s in new_sources:
        if new_s not in set_ids and new_s["Type"] in allowed_keys:
            existing_sources.append(new_s)
        elif new_s["Id"] not in allowed_keys:
            LOG.error(
                f"AWS Source type incorrect: {new_s['type']}. Expected one of {allowed_keys}"
            )


def handle_ingress_rules(source_config, ingress_config):
    LOG.debug("Source", dumps(source_config, indent=2))
    valid_keys = [
        (ServiceNetworking.self_key, bool, None),
        (Ingress.ext_sources_key, list, handle_ext_sources),
        (Ingress.aws_sources_key, list, handle_aws_sources),
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
                LOG.warning(
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
        Ingress.master_key: {
            ServiceNetworking.self_key: False,
            Ingress.ext_sources_key: [],
            Ingress.aws_sources_key: [],
        },
        "is_public": False,
    }
    valid_keys = [
        (Ingress.master_key, dict, handle_ingress_rules),
        ("use_cloudmap", bool, None),
        ("is_public", bool, None),
    ]
    x_network = [s.x_network for s in family.ordered_services if s.x_network]
    for config in valid_keys:
        for network in x_network:
            if config[0] in network:
                handle_merge_services_props(config, network, network_config)
    LOG.debug(family.name)
    LOG.debug(dumps(network_config, indent=2))
    return network_config


class ServiceNetworking(Ingress):
    """
    Class to group the configuration for Service network settings
    """

    self_key = "Myself"

    def __init__(self, family):
        """
        Initialize network settings for the family ServiceConfig

        :param ecs_composex.common.compose_services.ComposeFamily family:
        """
        self.ports = []
        self.merge_services_ports(family)
        self.configuration = merge_services_network(family)
        self.is_public = self.configuration["is_public"]
        self.ingress_from_self = True
        super().__init__(self.configuration[self.master_key], self.ports)
        self.add_self_ingress(family)

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

    def add_self_ingress(self, family):
        """
        Method to allow communications internally to the group on set ports
        :param troposphere.ec2.SecurityGroup sg:
        :param ecs_composex.common.compose_services.ComposeFamily family:
        :return:
        """
        if not family.template or not family.ecs_service or not self.ingress_from_self:
            return
        for port in self.ports:
            SecurityGroupIngress(
                f"AllowingMyselfToMyselfOnPort{port['published']}",
                template=family.template,
                FromPort=port["published"],
                ToPort=port["published"],
                IpProtocol=port["protocol"],
                GroupId=GetAtt(family.ecs_service.sg, "GroupId"),
                SourceSecurityGroupId=GetAtt(family.ecs_service.sg, "GroupId"),
                SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                Description=Sub(
                    f"Allowing traffic internally on port {port['published']}"
                ),
            )

    def add_lb_ingress(self, family, lb_name, lb_sg_ref):
        """
        Method to add ingress rules from other AWS Sources

        :param ecs_composex.common.compose_services.ComposeFamily family:
        :param str lb_name:
        :param lb_sg_ref:
        :return:
        """
        if not family.template or not family.ecs_service:
            return
        for port in self.ports:
            title = f"From{lb_name}ToServiceOn{port['published']}"
            common_args = {
                "FromPort": port["published"],
                "ToPort": port["published"],
                "IpProtocol": port["protocol"],
                "GroupId": GetAtt(family.ecs_service.sg, "GroupId"),
                "SourceSecurityGroupOwnerId": Ref(AWS_ACCOUNT_ID),
                "Description": Sub(
                    f"From {lb_name} to ${{{SERVICE_NAME_T}}} on port {port['published']}"
                ),
            }
            if title in family.template.resources:
                return
            SecurityGroupIngress(
                title,
                template=family.template,
                SourceSecurityGroupId=lb_sg_ref,
                **common_args,
            )
