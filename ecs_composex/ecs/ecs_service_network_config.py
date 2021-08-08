#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to help with defining the network settings for the ECS Service based on the family services definitions.
"""

from json import dumps

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import AWS_ACCOUNT_ID, GetAtt, Parameter, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.common import LOG, add_parameters
from ecs_composex.ecs.ecs_params import SERVICE_NAME_T
from ecs_composex.ingress_settings import Ingress, set_service_ports
from ecs_composex.vpc.vpc_params import SG_ID_TYPE


def handle_ext_sources(existing_sources, new_sources):
    LOG.debug("Source", dumps(existing_sources, indent=2))
    set_ipv4_sources = [
        s[Ingress.ipv4_key] for s in existing_sources if keyisset(Ingress.ipv4_key, s)
    ]
    for new_s in new_sources:
        if new_s not in set_ipv4_sources:
            existing_sources.append(new_s)


def handle_aws_sources(existing_sources, new_sources):
    """
    Function to handle merge of aws sources between two services for one family
    :param existing_sources:
    :param new_sources:
    :return:
    """
    LOG.debug("Source", dumps(existing_sources, indent=2))
    set_ids = [s["Id"] for s in existing_sources if keyisset("Id", s)]
    allowed_keys = ["PrefixList", "SecurityGroup"]
    for new_s in new_sources:
        if new_s not in set_ids and new_s["Type"] in allowed_keys:
            existing_sources.append(new_s)
        elif new_s["Id"] not in allowed_keys:
            LOG.error(
                f"AWS Source type incorrect: {new_s['type']}. Expected one of {allowed_keys}"
            )


def handle_services(existing_sources, new_sources):
    """
    Function to merge source services definitions

    :param list existing_sources:
    :param list new_sources:
    :return:
    """
    set_ids = [s["Name"] for s in existing_sources if keyisset("Name", s)]
    for new_s in new_sources:
        if new_s not in set_ids:
            existing_sources.append(new_s)


def handle_ingress_rules(source_config, ingress_config):
    LOG.debug("Source", dumps(source_config, indent=2))
    valid_keys = [
        (ServiceNetworking.self_key, bool, None),
        (Ingress.ext_sources_key, list, handle_ext_sources),
        (Ingress.aws_sources_key, list, handle_aws_sources),
        (Ingress.services_key, list, handle_services),
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
        "UseCloudmap": False,
        Ingress.master_key: {
            ServiceNetworking.self_key: False,
            Ingress.ext_sources_key: [],
            Ingress.aws_sources_key: [],
            Ingress.services_key: [],
        },
        "IsPublic": False,
    }
    valid_keys = [
        (Ingress.master_key, dict, handle_ingress_rules),
        ("UseCloudmap", bool, None),
        ("IsPublic", bool, None),
    ]
    x_network = [s.x_network for s in family.ordered_services if s.x_network]
    for config in valid_keys:
        if config[1] is bool and any(
            [cfg[config[0]] for cfg in x_network if keypresent(config[0], cfg)]
        ):
            LOG.info(
                f"At least one service of {family.name} is set to use {config[0]}. Enabling."
            )
            network_config[config[0]] = True
        else:
            for network in x_network:
                if config[0] in network:
                    handle_merge_services_props(config, network, network_config)

    LOG.debug(family.name)
    LOG.debug(dumps(network_config, indent=2))
    return network_config


def add_independant_rules(dst_family, service_name, root_stack):
    src_service_stack = root_stack.stack_template.resources[service_name]
    for port in dst_family.service_config.network.ports:
        ingress_rule = SecurityGroupIngress(
            f"From{src_service_stack.title}To{dst_family.logical_name}On{port['published']}",
            FromPort=port["published"],
            ToPort=port["published"],
            IpProtocol=port["protocol"],
            Description=Sub(
                f"From {src_service_stack.title} to {dst_family.logical_name}"
                f" on port {port['published']}/{port['protocol']}"
            ),
            GroupId=GetAtt(
                dst_family.stack.title,
                f"Outputs.{dst_family.logical_name}GroupId",
            ),
            SourceSecurityGroupId=GetAtt(
                src_service_stack.title,
                f"Outputs.{src_service_stack.title}GroupId",
            ),
            SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
        )
        if ingress_rule.title not in root_stack.stack_template.resources:
            root_stack.stack_template.add_resource(ingress_rule)


def set_compose_services_ingress(root_stack, dst_family, families, settings):
    """
    Function to crate SG Ingress between two families / services.
    Presently, the ingress rules are set after all services have been created

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.compose_services.ComposeFamily dst_family:
    :param list families: The list of family names.
    :return:
    """
    for service in dst_family.service_config.network.services:
        service_name = service["Name"]
        if service_name not in families:
            raise KeyError(
                f"The service {service_name} is not among the services created together. Valid services are",
                families,
            )
        if not keypresent("DependsOn", service):
            add_independant_rules(dst_family, service_name, root_stack)
        else:
            src_family = settings.families[service_name]
            if dst_family.stack.title not in src_family.stack.DependsOn:
                src_family.stack.DependsOn.append(dst_family.stack.title)
            dst_family_sg_param = Parameter(
                f"{dst_family.stack.title}GroupId", Type=SG_ID_TYPE
            )
            add_parameters(src_family.template, [dst_family_sg_param])
            src_family.stack.Parameters.update(
                {
                    dst_family_sg_param.title: GetAtt(
                        dst_family.stack.title,
                        f"Outputs.{dst_family.logical_name}GroupId",
                    ),
                }
            )
            for port in dst_family.service_config.network.ports:
                common_args = {
                    "FromPort": port["published"],
                    "ToPort": port["published"],
                    "IpProtocol": port["protocol"],
                    "SourceSecurityGroupOwnerId": Ref(AWS_ACCOUNT_ID),
                    "Description": Sub(
                        f"From ${{{SERVICE_NAME_T}}} to {dst_family.stack.title} on port {port['published']}"
                    ),
                }
                src_family.template.add_resource(
                    SecurityGroupIngress(
                        f"From{src_family.logical_name}To{dst_family.stack.title}On{port['published']}",
                        SourceSecurityGroupId=GetAtt(
                            src_family.ecs_service.sg, "GroupId"
                        ),
                        GroupId=Ref(dst_family_sg_param),
                        **common_args,
                    )
                )


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
        self.networks = {}
        self.merge_services_ports(family)
        self.merge_networks(family)
        self.configuration = merge_services_network(family)
        self.use_cloudmap = self.configuration["UseCloudmap"]
        self.is_public = self.configuration["IsPublic"]
        self.ingress_from_self = False
        super().__init__(self.configuration[self.master_key], self.ports)
        self.ingress_from_self = keyisset(self.self_key, self.definition)

    def merge_networks(self, family):
        """
        Method to merge network
        """
        for svc in family.services:
            if svc.networks:
                self.networks.update(svc.networks)

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

        :param ecs_composex.common.compose_services.ComposeFamily family:
        :return:
        """
        if not family.template or not family.ecs_service or not self.ingress_from_self:
            return
        for port in self.ports:
            self.to_self_rules.append(
                SecurityGroupIngress(
                    f"AllowingInterCommunicationPort{port['published']}{port['protocol']}",
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
            title = f"FromLB{lb_name}To{family.stack.title}On{port['target']}"
            common_args = {
                "FromPort": port["target"],
                "ToPort": port["target"],
                "IpProtocol": port["protocol"],
                "GroupId": GetAtt(family.ecs_service.sg, "GroupId"),
                "SourceSecurityGroupOwnerId": Ref(AWS_ACCOUNT_ID),
                "Description": Sub(
                    f"From ELB {lb_name} to ${{{SERVICE_NAME_T}}} on port {port['target']}"
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
