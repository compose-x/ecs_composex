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

from ipaddress import IPv4Interface
from json import dumps

from troposphere import AWS_ACCOUNT_ID, AWS_NO_VALUE
from troposphere import Sub, Ref, GetAtt
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common import keyisset, keypresent
from ecs_composex.ecs.ecs_params import SERVICE_NAME_T


def flatten_ip(ip_str):
    """
    Function to remove all non alphanum characters from IP CIDR notation

    :param ip_str:
    :rtype: str
    """
    return ip_str.replace(".", "").split("/")[0].strip()


def generate_security_group_props(allowed_source, service_name):
    """
    Function to parse the allowed source and create the SG Opening options accordingly.

    :param dict allowed_source: The allowed source defined in configs
    :param str service_name:
    :return: security group ingress properties
    :rtype: dict
    """
    props = {
        "CidrIp": (
            allowed_source["ipv4"]
            if keyisset("ipv4", allowed_source)
            else Ref(AWS_NO_VALUE)
        ),
        "CidrIpv6": (
            allowed_source["ipv6"]
            if keyisset("ipv6", allowed_source)
            else Ref(AWS_NO_VALUE)
        ),
    }

    if keyisset("CidrIp", props) and isinstance(props["CidrIp"], str):
        try:
            IPv4Interface(props["CidrIp"])
        except Exception as error:
            LOG.error(
                f"Falty IP Address: {allowed_source} - ecs_service {service_name}"
            )
            raise ValueError("Not a valid IPv4 CIDR notation", props["CidrIp"], error)
    return props


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
        """
        Initialize network settings for the family ServiceConfig

        :param ecs_composex.common.compose_services.ComposeFamily family:
        """
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
        self.tgt_groups = []

    def __repr__(self):
        return dumps(self.configuration, indent=2)

    def refresh(self, family):
        self.add_self_ingress(family)
        self.add_aws_sources(family)
        self.add_ext_sources_ingress(family)

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

    def validate_aws_sources(self):
        allowed_keys = ["type", "id"]
        allowed_types = ["SecurityGroup", "PrefixList"]
        for source in self.aws_sources:
            if not all(key in allowed_keys for key in source.keys()):
                raise KeyError(
                    "Missing ingress properties. Got",
                    source.keys,
                    "Expected",
                    allowed_keys,
                )
            if not source["type"] in allowed_types:
                raise ValueError(
                    "Invalid type specified. Got",
                    source["type"],
                    "Allowed one of ",
                    allowed_types,
                )

    def add_aws_sources(self, family):
        """
        Method to add ingress rules from other AWS Sources

        :param ecs_composex.common.compose_services.ComposeFamily family:
        :return:
        """
        if not family.template or not family.ecs_service:
            return
        self.validate_aws_sources()
        for source in self.aws_sources:
            for port in self.ports:
                common_args = {
                    "FromPort": port["published"],
                    "ToPort": port["published"],
                    "IpProtocol": port["protocol"],
                    "GroupId": GetAtt(family.ecs_service.sg, "GroupId"),
                    "SourceSecurityGroupOwnerId": Ref(AWS_ACCOUNT_ID),
                    "Description": Sub(
                        f"From {source['id']} to ${{{SERVICE_NAME_T}}} on port {port['published']}"
                    ),
                }
                if source["type"] == "SecurityGroup":
                    SecurityGroupIngress(
                        f"From{NONALPHANUM.sub('', source['id'])}ToServiceOn{port['published']}",
                        template=family.template,
                        SourceSecurityGroupId=source["id"],
                        **common_args,
                    )
                elif source["type"] == "PrefixList":
                    SecurityGroupIngress(
                        f"From{NONALPHANUM.sub('', source['id'])}ToServiceOn{port['published']}",
                        template=family.template,
                        SourcePrefixListId=source["id"],
                        **common_args,
                    )

    def create_ext_sources_ingress_rule(
        self, family, allowed_source, security_group, **props
    ):
        for port in self.ports:
            if keyisset("source_name", allowed_source):
                title = f"From{allowed_source['source_name'].title()}Onto{port['published']}{port['protocol']}"
                description = Sub(
                    f"From {allowed_source['source_name'].title()} "
                    f"To {port['published']}{port['protocol']} for ${{{SERVICE_NAME_T}}}"
                )
            else:
                title = (
                    f"From{flatten_ip(allowed_source['ipv4'])}"
                    f"To{port['published']}{port['protocol']}"
                )
                description = Sub(
                    f"Public {port['published']}{port['protocol']}"
                    f" for ${{{SERVICE_NAME_T}}}"
                )
            SecurityGroupIngress(
                title,
                template=family.template,
                Description=description,
                GroupId=GetAtt(security_group, "GroupId"),
                IpProtocol=port["protocol"],
                FromPort=port["published"],
                ToPort=port["published"],
                **props,
            )

    def add_ext_sources_ingress(self, family, security_group=None):
        """
        Method to add ingress rules from external sources to a given Security Group (ie. ALB Security Group).
        If a list of IPs is found in the config['ext_sources'] part of the network section of configs for the service,
        then it will use that. If no IPv4 source is indicated, it will by default allow traffic from 0.0.0.0/0

        :param security_group: security group (object or title string) to add the rules to
        :type security_group: str or troposphere.ec2.SecurityGroup
        :param ecs_composex.common.compose_services.ComposeFamily family:
        """
        if not security_group:
            security_group = family.ecs_service.sg
        if not self.ext_sources and self.is_public:
            self.ext_sources = [
                {"ipv4": "0.0.0.0/0", "protocol": -1, "source_name": "ANY"}
            ]

        for allowed_source in self.ext_sources:
            if not keyisset("ipv4", allowed_source) and not keyisset(
                "ipv6", allowed_source
            ):
                LOG.warn("No IPv4 or IPv6 set. Skipping")
                continue
            props = generate_security_group_props(allowed_source, family.logical_name)
            if props:
                LOG.debug(f"Adding {allowed_source} for ingress")
                self.create_ext_sources_ingress_rule(
                    family, allowed_source, security_group, **props
                )
