# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage the AppMesh Virtual service
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from .appmesh_mesh import Mesh
    from .appmesh_node import MeshNode
    from .appmesh_router import MeshRouter
    from ecs_composex.common.settings import ComposeXSettings

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, GetAtt, Ref, Select, Split, Sub, appmesh
from troposphere.servicediscovery import DnsConfig as SdDnsConfig
from troposphere.servicediscovery import DnsRecord as SdDnsRecord
from troposphere.servicediscovery import Instance as SdInstance
from troposphere.servicediscovery import Service as SdService

from ecs_composex.appmesh import appmesh_conditions
from ecs_composex.appmesh.appmesh_params import NODE_KEY, ROUTER_KEY, ROUTERS_KEY
from ecs_composex.cloudmap.cloudmap_params import (
    PRIVATE_DNS_ZONE_NAME,
    PRIVATE_NAMESPACE_ID,
)
from ecs_composex.common import NONALPHANUM
from ecs_composex.common.troposphere_tools import (
    add_parameters,
    add_resource,
    add_update_mapping,
)


def validate_service_backend(service, routers, nodes):
    """
    Function to validate backend settings

    :param service:
    :param nodes:
    :param routers:
    :raises: KeyError
    """
    if keyisset(ROUTER_KEY, service) and service[ROUTER_KEY] not in routers.keys():
        raise KeyError(
            "Routers provided not found in the routers description. Got",
            service[ROUTERS_KEY],
            "Expected",
            routers.keys(),
        )
    if keyisset(NODE_KEY, service) and service[NODE_KEY] not in nodes.keys():
        raise KeyError(
            "Nodes provided not found in nodes defined. Got",
            service[NODE_KEY],
            "Expected one of",
            nodes.keys(),
        )


class MeshService:
    """
    Class to represent a mesh Virtual Service.
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        routers: Mapping[str, MeshRouter],
        nodes: Mapping[str, MeshNode],
        mesh: Mesh,
        settings: ComposeXSettings,
    ):
        """
        Method to initialize the Mesh service.

        :param name: name of the virtual service
        :param routers: the routers of the mesh
        :param nodes: the nodes of the mesh
        :param mesh: the mesh object.
        """
        self.title = NONALPHANUM.sub("", name)
        self.definition = definition
        self._namespace = settings.find_resource(
            f"x-cloudmap::{self.definition['x-cloudmap']}"
        )
        service_node = (
            nodes[self.definition[NODE_KEY]]
            if keyisset(NODE_KEY, self.definition)
            else None
        )
        service_router = (
            routers[self.definition[ROUTER_KEY]]
            if keyisset(ROUTER_KEY, self.definition)
            else None
        )
        if not service_router and not service_node:
            raise AttributeError(
                f"The service {name} has neither nodes or routers defined. Define at least one"
            )
        depends = []
        self.node = service_node if service_node else None
        self.router = service_router if service_router else None

        self.service = appmesh.VirtualService(
            f"{NONALPHANUM.sub('', name).title()}VirtualService",
            DependsOn=depends,
            MeshName=appmesh_conditions.get_mesh_name(mesh.appmesh),
            MeshOwner=appmesh_conditions.set_mesh_owner_id(),
            VirtualServiceName=Sub(
                f"{name}.${{ZoneName}}",
                ZoneName=self.namespace_property(
                    PRIVATE_DNS_ZONE_NAME, mesh.stack, settings
                ),
            ),
            Spec=appmesh.VirtualServiceSpec(
                Provider=appmesh.VirtualServiceProvider(
                    VirtualNode=appmesh.VirtualNodeServiceProvider(
                        VirtualNodeName=GetAtt(service_node.node, "VirtualNodeName")
                    )
                    if service_node
                    else Ref(AWS_NO_VALUE),
                    VirtualRouter=appmesh.VirtualRouterServiceProvider(
                        VirtualRouterName=GetAtt(
                            service_router.router, "VirtualRouterName"
                        )
                    )
                    if service_router
                    else Ref(AWS_NO_VALUE),
                )
            ),
        )

    def namespace_property(self, property_param, stack, settings: ComposeXSettings):
        if not self._namespace:
            return Ref(AWS_NO_VALUE)
        _id = self._namespace.attributes_outputs[property_param]
        if self._namespace.cfn_resource:
            add_parameters(stack.stack_template, [_id["ImportParameter"]])
            stack.Parameters.update({_id["ImportParameter"].title: _id["ImportValue"]})
            return Ref(_id["ImportParameter"])
        elif self._namespace.mappings:
            add_update_mapping(
                stack.stack_template,
                self._namespace.module.mapping_key,
                settings.mappings[self._namespace.module.mapping_key],
            )
            return _id["ImportValue"]

    def add_dns_entries(self, stack, settings):
        """
        Method to add CloudMap service and record for DNS resolution.
        """
        sd_entry = SdService(
            f"{self.title.title()}ServiceDiscovery",
            DependsOn=[self.service.title],
            Description=Sub(
                f"Record for VirtualService {self.title} in mesh ${{{self.service.title}.MeshName}}"
            ),
            NamespaceId=self.namespace_property(PRIVATE_NAMESPACE_ID, stack, settings),
            DnsConfig=SdDnsConfig(
                RoutingPolicy="MULTIVALUE",
                NamespaceId=Ref(AWS_NO_VALUE),
                DnsRecords=[SdDnsRecord(TTL="30", Type="A")],
            ),
            Name=Select(0, Split(".", GetAtt(self.service, "VirtualServiceName"))),
        )
        instance = SdInstance(
            f"{self.title.title()}ServiceDiscoveryFakeInstance",
            InstanceAttributes={"AWS_INSTANCE_IPV4": "169.254.255.254"},
            ServiceId=Ref(sd_entry),
        )
        add_resource(stack.stack_template, sd_entry)
        add_resource(stack.stack_template, instance)

    def get_backend_nodes(self):
        """
        Method to return the nodes SG when this service is used as backend.

        :return:
        """
        if self.node:
            return [self.node]
        elif self.router:
            return [node for node in self.router.nodes]
