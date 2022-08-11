# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to help with defining the network settings for the ECS Service based on the family services definitions.
"""

import re
from copy import deepcopy
from ipaddress import IPv4Interface
from json import dumps

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_ACCOUNT_ID, AWS_NO_VALUE, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.common.logging import LOG


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


def set_port_from_str(port: str):
    """
    Function to filter out port string and define published port, target port and protocol

    :param str port:
    :return: the ports parameters
    :rtype: tuple
    """
    if r"/" in port:
        protocol = port.split(r"/")[-1]
        if protocol not in ["udp", "tcp"]:
            raise ValueError(
                "Protocol", protocol, "is not valid. Must be one of", ["udp", "tcp"]
            )
        port = port.split(r"/")[0]
    else:
        protocol = "tcp"
    if r":" in port:
        published = port.split(r":")[0]
        target = port.split(r":")[1]
    else:
        target = port
        published = port
    if r"-" in target or r"-" in published:
        raise ValueError(
            "Range ports not supported for exposure in AWS ECS with AWSVPC mode"
        )
    numbers_only = re.compile(r"^\d+$")
    if not numbers_only.match(target):
        raise ValueError("target port is not valid", numbers_only.pattern)
    if not numbers_only.match(published):
        raise ValueError("published port is not valid", numbers_only.pattern)
    if not (1 <= int(target) < (2**16)):
        raise ValueError(f"target port {target} is not between 1 and 65535")
    if not (1 <= int(published) < (2**16)):
        raise ValueError(f"published port {published} is not between 1 and 65535")

    return published, target, protocol


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
            parts = set_port_from_str(port)
            service_ports.append(
                {
                    "protocol": parts[2],
                    "published": int(parts[0]),
                    "target": int(parts[1]),
                }
            )
        elif isinstance(port, dict):
            service_ports.append(port)
        elif isinstance(port, int):
            service_ports.append(
                {
                    "protocol": "tcp",
                    "published": port,
                    "target": port,
                }
            )
    return service_ports


def lookup_security_group(settings, lookup):
    """
    Function to fetch the security group ID based on lookup details

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param lookup:
    :return:
    """
    sg_re = re.compile(
        r"^arn:aws(?:-[a-z]+)?:ec2:[a-z0-9-]+:\d{12}:security-group/([\S]+)$"
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


class Ingress:
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
        self.ext_sources = []
        if keyisset(self.ext_sources_key, self.definition):
            cidrs = []
            for ext_source in self.definition[self.ext_sources_key]:
                source_cidr = set_else_none(
                    self.ipv4_key,
                    ext_source,
                    set_else_none(self.ipv6_key, ext_source, None),
                )
                if source_cidr and source_cidr not in cidrs:
                    self.ext_sources.append(ext_source)
                else:
                    LOG.warning(
                        f"Ingress source {source_cidr} already defined in a previous Ingress rule."
                    )

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

    def set_aws_sources_ingress(self, settings, destination_title, sg_ref) -> None:
        """
        Method to define AWS Sources ingresses

        :param settings:
        :param destination_title:
        :param sg_ref:
        """
        for source in self.aws_sources:
            for port in self.ports:
                if (
                    keyisset("Ports", source)
                    and port["published"] not in source["Ports"]
                ):
                    continue
                target_port = set_else_none(
                    "published", port, alt_value=set_else_none("target", port, None)
                )
                if target_port is None:
                    raise ValueError(
                        "Wrong port definition value for security group ingress", port
                    )
                common_args = {
                    "FromPort": target_port,
                    "ToPort": target_port,
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
                                f"From {sg_id} to {destination_title} on port {target_port}"
                            )
                        }
                    )
                    self.aws_ingress_rules.append(
                        SecurityGroupIngress(
                            f"From{NONALPHANUM.sub('', sg_id)}ToServiceOn{target_port}",
                            SourceSecurityGroupId=sg_id,
                            SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                            **common_args,
                        )
                    )
                elif source["Type"] == "PrefixList":
                    self.aws_ingress_rules.append(
                        SecurityGroupIngress(
                            f"From{NONALPHANUM.sub('', source['Id'])}ToServiceOn{target_port}",
                            SourcePrefixListId=source["Id"],
                            **common_args,
                        )
                    )

    def create_ext_sources_ingress_rule(
        self, destination_title, allowed_source, security_group, **props
    ) -> None:
        """
        Creates the Security Ingress rule for a CIDR based rule

        :param str destination_title:
        :param dict allowed_source:
        :param security_group:
        :param dict props:
        """
        for port in self.ports:
            target_port = set_else_none(
                "published", port, alt_value=set_else_none("target", port, None)
            )
            if target_port is None:
                raise ValueError(
                    "Wrong port definition value for security group ingress", port
                )
            if (
                keyisset("Ports", allowed_source)
                and target_port not in allowed_source["Ports"]
            ):
                continue
            if keyisset("Name", allowed_source):
                name = NONALPHANUM.sub("", allowed_source["Name"])
                title = f"From{name.title()}To{target_port}{port['protocol']}"
                description = Sub(
                    f"From {name.title()} "
                    f"To {target_port}{port['protocol']} for {destination_title}"
                )
            else:
                title = (
                    f"From{flatten_ip(allowed_source[self.ipv4_key])}"
                    f"To{target_port}{port['protocol']}"
                )
                description = Sub(
                    f"Public {target_port}{port['protocol']}"
                    f" for {destination_title}"
                )
            self.ext_ingress_rules.append(
                SecurityGroupIngress(
                    title,
                    Description=description
                    if not keyisset("Description", allowed_source)
                    else allowed_source["Description"],
                    GroupId=security_group,
                    IpProtocol=port["protocol"],
                    FromPort=target_port,
                    ToPort=target_port,
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
            LOG.debug("No external rules defined. Skipping.")
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

    def associate_aws_ingress_rules(self, template):
        """
        Method to associate AWS ingress rules to a specific template

        :param troposphere.Template template:
        :return:
        """
        for ingress_rule in self.aws_ingress_rules:
            if ingress_rule.title not in template.resources:
                template.add_resource(ingress_rule)

    def associate_ext_ingress_rules(self, template):
        """
        Method to associate External ingress rules to a specific template

        :param troposphere.Template template:
        :return:
        """
        for ingress_rule in self.ext_ingress_rules:
            if ingress_rule.title not in template.resources:
                template.add_resource(ingress_rule)
