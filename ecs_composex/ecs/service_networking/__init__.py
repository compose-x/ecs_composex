#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to help with defining the network settings for the ECS Service based on the family services definitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from itertools import chain

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_ACCOUNT_ID, GetAtt, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_params import NETWORK_MODE, SERVICE_NAME_T
from ecs_composex.ecs.service_networking.ingress_helpers import (
    merge_cloudmap_settings,
    merge_family_services_networking,
)
from ecs_composex.ingress_settings import Ingress, set_service_ports


class ServiceNetworking(object):
    """
    Class to group the configuration for Service network settings

    :ivar list[dict] ports: List of the ports used by te service
    :ivar dict networks: Mapping of the networks to use for service
    """

    self_key = "Myself"

    def __init__(self, family: ComposeFamily):
        """
        Initialize network settings for the family ServiceConfig

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        """
        self.family = family
        self._network_mode = "awsvpc"
        if family.launch_type == "EXTERNAL":
            LOG.warning(
                f"{family.name} - External mode cannot use awsvpc mode. Falling back to bridge"
            )
            self.network_mode = "bridge"
        self.ports = []
        self.networks = {}
        self.merge_services_ports()
        self.merge_networks()
        self.definition = merge_family_services_networking(family)
        self.ingress_from_self = False
        if any([svc.expose_ports for svc in family.services]):
            self.ingress_from_self = True
            LOG.info(
                f"{family.name} - services have export ports, allowing internal ingress"
            )
        self.security_group = None
        self.cloudmap_config = (
            merge_cloudmap_settings(family, self.ports) if self.ports else {}
        )
        self.ingress = Ingress(self.definition[Ingress.master_key], self.ports)
        self.ingress_from_self = keyisset(self.self_key, self.definition)

    @property
    def network_mode(self):
        """
        The network mode used for the Task/Service. valid are host/bridge/awsvpc.
        Defaults to awsvpc. Only override is to bridge/host based on the Launch Type
        """
        return self._network_mode

    @network_mode.setter
    def network_mode(self, mode: str):
        self._network_mode = mode
        self.family.stack.Parameters.update({NETWORK_MODE.title: self._network_mode})

    def merge_networks(self):
        """
        Method to merge network
        """
        for svc in self.family.services:
            if svc.networks:
                self.networks.update(svc.networks)

    def merge_services_ports(self):
        """
        Function to merge two sections of ports

        :return:
        """
        source_ports = [
            service.ports
            for service in chain(
                self.family.managed_sidecars, self.family.ordered_services
            )
            if service.ports
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

    def add_self_ingress(self) -> None:
        """
        Method to allow communications internally to the group on set ports
        """
        if (
            not self.family.template
            or not self.family.ecs_service
            or not self.ingress_from_self
        ):
            return
        for port in self.ports:
            target_port = set_else_none(
                "published", port, alt_value=set_else_none("target", port, None)
            )
            if target_port is None:
                raise ValueError(
                    "Wrong port definition value for security group ingress", port
                )
            self.ingress.to_self_rules.append(
                SecurityGroupIngress(
                    f"AllowingInterCommunicationPort{target_port}{port['protocol']}",
                    template=self.family.template,
                    FromPort=target_port,
                    ToPort=target_port,
                    IpProtocol=port["protocol"],
                    GroupId=GetAtt(
                        self.family.service_networking.security_group, "GroupId"
                    ),
                    SourceSecurityGroupId=GetAtt(
                        self.family.service_networking.security_group, "GroupId"
                    ),
                    SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                    Description=Sub(
                        f"Allowing traffic internally on port {target_port}"
                    ),
                )
            )

    def add_lb_ingress(self, lb_name, lb_sg_ref) -> None:
        """
        Method to add ingress rules from other AWS Sources

        :param str lb_name:
        :param lb_sg_ref:
        :return:
        """
        if not self.family.template or not self.family.ecs_service:
            return
        for port in self.ports:
            title = f"FromLB{lb_name}To{self.family.stack.title}On{port['target']}"
            common_args = {
                "FromPort": port["target"],
                "ToPort": port["target"],
                "IpProtocol": port["protocol"],
                "GroupId": GetAtt(
                    self.family.service_networking.security_group, "GroupId"
                ),
                "SourceSecurityGroupOwnerId": Ref(AWS_ACCOUNT_ID),
                "Description": Sub(
                    f"From ELB {lb_name} to ${{{SERVICE_NAME_T}}} on port {port['target']}"
                ),
            }
            if title in self.family.template.resources:
                return
            SecurityGroupIngress(
                title,
                template=self.family.template,
                SourceSecurityGroupId=lb_sg_ref,
                **common_args,
            )
