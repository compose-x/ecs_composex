#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cloudmap_stack import PrivateNamespace
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack

from troposphere import AWS_NO_VALUE, GetAtt, Output, Ref, Sub
from troposphere.ecs import ServiceRegistry
from troposphere.servicediscovery import DnsConfig, DnsRecord, HealthCheckCustomConfig
from troposphere.servicediscovery import Service as SdService

from ecs_composex.cloudmap.cloudmap_params import (
    ECS_SERVICE_NAMESPACE_SERVICE_ARN,
    ECS_SERVICE_NAMESPACE_SERVICE_ID,
    ECS_SERVICE_NAMESPACE_SERVICE_NAME,
)
from ecs_composex.cloudmap.cloudmap_params import LABEL as CLOUDMAP_LABEL
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
)


def create_registry(family, namespace, port_config, settings):
    """
    Creates the settings for the ECS Service Registries and adds the resources to the appropriate template

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param ecs_composex.cloudmap.cloudmap_stack.PrivateNamespace namespace:
    :param dict port_config:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if family.ecs_service.registries:
        LOG.warn(
            f"{family.name} already has a CloudMap mapping. "
            f"Only one can be set. Ignoring mapping to {namespace.name}"
        )
        return
    family_sd_service = EcsDiscoveryService(family, namespace, port_config, settings)
    add_resource(namespace.stack.stack_template, family_sd_service.sd_service)
    family.service_networking.sd_service = family_sd_service


class EcsDiscoveryService:
    """
    Manages CloudMap Service Discovery service for a given family
    """

    def __init__(
        self,
        family: ComposeFamily,
        namespace: PrivateNamespace,
        port_config: dict,
        settings: ComposeXSettings,
    ):
        self.family = family
        self.namespace = namespace
        self.port_config = port_config

        self._sd_service = SdService(
            f"{namespace.logical_name}EcsServiceDiscovery{family.logical_name}",
            Description=Sub(f"{self.family.name} service"),
            NamespaceId=Ref(self.namespace.cfn_resource)
            if self.namespace.cfn_resource
            else self.namespace.namespace_id["ImportValue"],
            HealthCheckCustomConfig=HealthCheckCustomConfig(FailureThreshold=1.0),
            DnsConfig=DnsConfig(
                RoutingPolicy="MULTIVALUE",
                NamespaceId=Ref(AWS_NO_VALUE),
                DnsRecords=[
                    DnsRecord(TTL="15", Type="A"),
                    DnsRecord(TTL="15", Type="SRV"),
                ],
            ),
            Name=family.family_hostname,
        )

        self._sd_service_parameter = Parameter(
            self._sd_service.title,
            group_label=CLOUDMAP_LABEL,
            Type="String",
            Description=Sub(
                f"Service Discovery Service for {family.family_hostname} - ${{AWS_STACK_NAME}}",
                AWS_STACK_NAME=define_stack_name(),
            ),
        )

        add_resource(self.namespace.stack.stack_template, self.sd_service)
        self.output_attributes = {
            ECS_SERVICE_NAMESPACE_SERVICE_ARN: (
                f"{self.sd_service.title}{ECS_SERVICE_NAMESPACE_SERVICE_ARN.return_value}",
                self.sd_service,
                GetAtt,
                ECS_SERVICE_NAMESPACE_SERVICE_ARN.return_value,
            ),
            ECS_SERVICE_NAMESPACE_SERVICE_ID: (
                f"{self.sd_service.title}{ECS_SERVICE_NAMESPACE_SERVICE_ID.return_value}",
                self.sd_service,
                GetAtt,
                ECS_SERVICE_NAMESPACE_SERVICE_ID.return_value,
            ),
            ECS_SERVICE_NAMESPACE_SERVICE_NAME: (
                f"{self.sd_service.title}{ECS_SERVICE_NAMESPACE_SERVICE_NAME.return_value}",
                self.sd_service,
                GetAtt,
                ECS_SERVICE_NAMESPACE_SERVICE_NAME.return_value,
            ),
        }

        add_outputs(
            self.namespace.stack.stack_template,
            [_attr["Output"] for _attr in self.attributes_properties.values()],
        )

    @property
    def sd_service(self) -> SdService:
        return self._sd_service

    @property
    def sd_family_parameter(self) -> Parameter:
        return self._sd_service_parameter

    @property
    def ecs_service_registry(self) -> ServiceRegistry:
        add_parameters(
            self.family.template,
            [
                self.attributes_properties[ECS_SERVICE_NAMESPACE_SERVICE_ARN][
                    "ImportParameter"
                ]
            ],
        )
        self.family.stack.Parameters.update(
            {
                self.attributes_properties[ECS_SERVICE_NAMESPACE_SERVICE_ARN][
                    "ImportParameter"
                ].title: self.attributes_properties[ECS_SERVICE_NAMESPACE_SERVICE_ARN][
                    "ImportValue"
                ]
            }
        )
        return ServiceRegistry(
            f"ServiceRegistry{self.port_config['target']}",
            RegistryArn=Ref(
                self.attributes_properties[ECS_SERVICE_NAMESPACE_SERVICE_ARN][
                    "ImportParameter"
                ]
            ),
            Port=int(self.port_config["target"]),
        )

    @property
    def attributes_properties(self) -> dict:
        attributes = {}
        for parameter, definition in self.output_attributes.items():
            _attr_parameter = Parameter(
                definition[0], group_label=CLOUDMAP_LABEL, Type="String"
            )
            _attr_output = (
                Output(definition[0], Value=definition[2](definition[1], definition[3]))
                if definition[2] is GetAtt
                else Output(definition[0], Value=definition[2])
            )
            _attr_import = GetAtt(
                self.namespace.stack.title, f"Outputs.{definition[0]}"
            )
            attributes[parameter] = {
                "ImportParameter": _attr_parameter,
                "ImportValue": _attr_import,
                "Output": _attr_output,
            }
        return attributes

    def set_update_attribute(self, attribute: Parameter, dest_stack: ComposeXStack):
        """
        Adds the parameter to the destination stack, updates the parameters, and returns the
        parameter pointer

        :param attribute:
        :param dest_stack:
        :return:
        """
        target_attribute = self.attributes_properties[attribute]
        add_parameters(dest_stack.stack_template, [target_attribute["ImportParameter"]])
        dest_stack.Parameters.update(
            {target_attribute["ImportParameter"].title: target_attribute["ImportValue"]}
        )
        if self.namespace.stack.title not in dest_stack.DependsOn:
            dest_stack.DependsOn.append(self.namespace.stack.title)
        return Ref(target_attribute["ImportParameter"])
