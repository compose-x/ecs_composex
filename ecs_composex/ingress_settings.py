#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to help with defining the network settings for the ECS Service based on the family services definitions.
"""

import re
from copy import deepcopy
from ipaddress import IPv4Interface
from json import dumps

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_NO_VALUE, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)


def flatten_ip(ip_str):
    """
    Function to remove all non alphanum characters from IP CIDR notation

    :param ip_str:
    :rtype: str
    """
    return str(ip_str.replace(".", "").split("/")[0].strip())


def generate_security_group_props(allowed_source):
    """
    Function to parse the allowed source and create the SG Opening options accordingly.

    :param dict allowed_source: The allowed source defined in configs
    :return: security group ingress properties
    :rtype: dict
    """
    props = {
        "CidrIp": (
            allowed_source[Ingress.ipv4_key]
            if keyisset(Ingress.ipv4_key, allowed_source)
            else Ref(AWS_NO_VALUE)
        ),
        "CidrIpv6": (
            allowed_source[Ingress.ipv6_key]
            if keyisset(Ingress.ipv6_key, allowed_source)
            else Ref(AWS_NO_VALUE)
        ),
    }
    if keyisset("CidrIp", props) and isinstance(props["CidrIp"], str):
        try:
            IPv4Interface(props["CidrIp"])
        except Exception as error:
            LOG.error(f"Falty IP Address: {allowed_source}")
            raise ValueError("Not a valid IPv4 CIDR notation", props["CidrIp"], error)
    return props


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


def lookup_security_group(settings, lookup):
    """
    Function to fetch the security group ID based on lookup details

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param lookup:
    :return:
    """
    sg_re = re.compile(
        r"(?:^arn:aws(?:-[a-z]+)?:ec2:[a-z0-9-]+:\d{12}:security-group/)([\S]+)$"
    )
    ec2_types = {
        "ec2:security-group": {"regexp": sg_re.pattern},
    }
    lookup_session = define_lookup_role_from_info(lookup, settings.session)
    sg_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "ec2:security-group",
        types=ec2_types,
    )
    if not sg_arn:
        raise LookupError("Failed to identify EC2 SecurityGroup based on tags")
    return sg_re.match(sg_arn).groups()[0]


class Ingress(object):
    """
    Class to group the configuration for Service network settings
    """

    defined = True

    master_key = "Ingress"
    aws_sources_key = "AwsSources"
    ext_sources_key = "ExtSources"
    services_key = "Services"
    ipv4_key = "IPv4"
    ipv6_key = "IPv6"
    network_settings = [master_key, "UseCloudmap", "IsPublic"]

    def __init__(self, definition, ports):
        """
        Initialize network settings for the family ServiceConfig
        """
        self.definition = deepcopy(definition)

        self.aws_sources = (
            self.definition[self.aws_sources_key]
            if keyisset(self.aws_sources_key, self.definition)
            else []
        )
        self.ext_sources = (
            self.definition[self.ext_sources_key]
            if keyisset(self.ext_sources_key, self.definition)
            else []
        )
        self.ext_sources = [
            dict(y) for y in set(tuple(x.items()) for x in self.ext_sources)
        ]
        self.services = (
            self.definition[self.services_key]
            if keyisset(self.services_key, self.definition)
            else []
        )
        self.ports = ports
        self.aws_ingress_rules = []
        self.ext_ingress_rules = []
        self.to_self_rules = []

    def __repr__(self):
        return dumps(self.definition, indent=2)

    def validate_aws_sources(self):
        allowed_keys = ["Type", "Id", "Lookup"]
        allowed_types = ["SecurityGroup", "PrefixList"]
        for source in self.aws_sources:
            if not all(key in allowed_keys for key in source.keys()):
                raise KeyError(
                    "Missing ingress properties. Got",
                    source.keys,
                    "Expected",
                    allowed_keys,
                )
            if not source["Type"] in allowed_types:
                raise ValueError(
                    "Invalid type specified. Got",
                    source["Type"],
                    "Allowed one of ",
                    allowed_types,
                )

    def set_aws_sources(self, settings, destination_title, sg_ref):
        """
        Method to define AWS Sources ingresses

        :param destination_title:
        :param sg_ref:
        :return:
        """
        self.validate_aws_sources()
        for source in self.aws_sources:
            for port in self.ports:
                common_args = {
                    "FromPort": port["published"],
                    "ToPort": port["published"],
                    "IpProtocol": port["protocol"],
                    "GroupId": sg_ref,
                }
                if source["Type"] == "SecurityGroup":
                    if keyisset("Id", source):
                        sg_id = source["Id"]
                    elif keyisset("Lookup", source):
                        sg_id = lookup_security_group(settings, source["Lookup"])
                    else:
                        raise KeyError(
                            "Information missing to identify the SecurityGroup. Requires either Id or Lookup"
                        )
                    common_args.update(
                        {
                            "Description": Sub(
                                f"From {sg_id} to {destination_title} on port {port['published']}"
                            )
                        }
                    )
                    self.aws_ingress_rules.append(
                        SecurityGroupIngress(
                            f"From{NONALPHANUM.sub('', sg_id)}ToServiceOn{port['published']}",
                            SourceSecurityGroupId=sg_id,
                            SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                            **common_args,
                        )
                    )
                elif source["Type"] == "PrefixList":
                    self.aws_ingress_rules.append(
                        SecurityGroupIngress(
                            f"From{NONALPHANUM.sub('', source['Id'])}ToServiceOn{port['published']}",
                            SourcePrefixListId=source["Id"],
                            **common_args,
                        )
                    )

    def create_ext_sources_ingress_rule(
        self, destination_tile, allowed_source, security_group, **props
    ):
        for port in self.ports:
            if keyisset("Name", allowed_source):
                name = NONALPHANUM.sub("", allowed_source["Name"])
                title = f"From{name.title()}To{port['published']}{port['protocol']}"
                description = Sub(
                    f"From {name.title()} "
                    f"To {port['published']}{port['protocol']} for {destination_tile}"
                )
            else:
                title = (
                    f"From{flatten_ip(allowed_source[self.ipv4_key])}"
                    f"To{port['published']}{port['protocol']}"
                )
                description = Sub(
                    f"Public {port['published']}{port['protocol']}"
                    f" for {destination_tile}"
                )
            self.ext_ingress_rules.append(
                SecurityGroupIngress(
                    title,
                    Description=description
                    if not keyisset("Description", allowed_source)
                    else allowed_source["Description"],
                    GroupId=security_group,
                    IpProtocol=port["protocol"],
                    FromPort=port["published"],
                    ToPort=port["published"],
                    **props,
                )
            )

    def set_ext_sources_ingress(self, destination_tile, security_group):
        """
        Method to add ingress rules from external sources to a given Security Group (ie. ALB Security Group).
        If a list of IPs is found in the config['ext_sources'] part of the network section of configs for the service,
        then it will use that. If no IPv4 source is indicated, it will by default allow traffic from 0.0.0.0/0

        :param str destination_tile: The name of the destination for description
        :param security_group: security group (object or title string) to add the rules to
        :type security_group: str or troposphere.ec2.SecurityGroup or troposphere.Ref or Troposphere.GetAtt
        """
        if not self.ext_sources:
            LOG.info("No external rules defined. Skipping.")
            return

        for allowed_source in self.ext_sources:
            if not keyisset(self.ipv4_key, allowed_source) and not keyisset(
                self.ipv6_key, allowed_source
            ):
                LOG.warning(f"No {self.ipv4_key} or {self.ipv6_key} set. Skipping")
                continue
            props = generate_security_group_props(allowed_source)
            if props:
                LOG.debug(f"Adding {allowed_source} for ingress")
                self.create_ext_sources_ingress_rule(
                    destination_tile, allowed_source, security_group, **props
                )

    def associate_aws_igress_rules(self, template):
        """
        Method to associate AWS ingress rules to a specific template

        :param troposphere.Template template:
        :return:
        """
        for ingress_rule in self.aws_ingress_rules:
            if ingress_rule.title not in template.resources:
                template.add_resource(ingress_rule)

    def associate_ext_igress_rules(self, template):
        """
        Method to associate External ingress rules to a specific template

        :param troposphere.Template template:
        :return:
        """
        for ingress_rule in self.ext_ingress_rules:
            if ingress_rule.title not in template.resources:
                template.add_resource(ingress_rule)
