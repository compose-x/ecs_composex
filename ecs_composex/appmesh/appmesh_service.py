#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage the AppMesh Virtual service
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, GetAtt, Ref, Select, Split, Sub, appmesh
from troposphere.servicediscovery import DnsConfig as SdDnsConfig
from troposphere.servicediscovery import DnsRecord as SdDnsRecord
from troposphere.servicediscovery import Instance as SdInstance
from troposphere.servicediscovery import Service as SdService

from ecs_composex.appmesh import appmesh_conditions
from ecs_composex.appmesh.appmesh_params import NODE_KEY, ROUTER_KEY, ROUTERS_KEY
from ecs_composex.common import NONALPHANUM


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


class MeshService(object):
    """
    Class to represent a mesh Virtual Service.
    """

    def __init__(self, name, definition, routers, nodes, mesh, dns_settings):
        """
        Method to initialize the Mesh service.

        :param name: name of the virtual service
        :param routers: the routers of the mesh
        :param nodes: the nodes of the mesh
        :param mesh: the mesh object.
        """
        self.title = NONALPHANUM.sub("", name)
        self.definition = definition
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
            MeshName=appmesh_conditions.get_mesh_name(mesh),
            MeshOwner=appmesh_conditions.set_mesh_owner_id(),
            VirtualServiceName=Sub(
                f"{name}.${{ZoneName}}", ZoneName=dns_settings.private_zone.name_value
            ),
            Spec=appmesh.VirtualServiceSpec(
                Provider=appmesh.VirtualServiceProvider(
                    VirtualNode=appmesh.VirtualNodeServiceProvider(
                        VirtualNodeName=service_node.get_node_param
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

    def add_dns_entries(self, template, dns_settings):
        """
        Method to add CloudMap service and record for DNS resolution.
        """
        sd_entry = SdService(
            f"{self.title.title()}ServiceDiscovery",
            template=template,
            DependsOn=[self.service.title],
            Description=Sub(
                f"Record for VirtualService {self.title} in mesh ${{{self.service.title}.MeshName}}"
            ),
            NamespaceId=dns_settings.private_zone.id_value,
            DnsConfig=SdDnsConfig(
                RoutingPolicy="MULTIVALUE",
                NamespaceId=Ref(AWS_NO_VALUE),
                DnsRecords=[SdDnsRecord(TTL="30", Type="A")],
            ),
            Name=Select(0, Split(".", GetAtt(self.service, "VirtualServiceName"))),
        )
        SdInstance(
            f"{self.title.title()}ServiceDiscoveryFakeInstance",
            template=template,
            InstanceAttributes={"AWS_INSTANCE_IPV4": "169.254.255.254"},
            ServiceId=Ref(sd_entry),
        )

    def get_backend_nodes(self):
        """
        Method to return the nodes SG when this service is used as backend.

        :return:
        """
        if self.node:
            return [self.node]
        elif self.router:
            return [node for node in self.router.nodes]
