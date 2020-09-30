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
Module to manage the AppMesh Virtual service
"""

from troposphere import AWS_NO_VALUE
from troposphere import Ref, Sub, GetAtt, Select, Split
from troposphere import appmesh
from troposphere.servicediscovery import (
    DnsConfig as SdDnsConfig,
    Service as SdService,
    DnsRecord as SdDnsRecord,
    Instance as SdInstance,
)

from ecs_composex.appmesh import appmesh_conditions
from ecs_composex.common import NONALPHANUM, keyisset
from ecs_composex.dns.dns_params import (
    PRIVATE_DNS_ZONE_ID,
    PRIVATE_DNS_ZONE_NAME,
)


def validate_service_backend(service, routers, nodes):
    """
    Function to validate backend settings

    :param service:
    :param nodes:
    :param routers:
    :raises: KeyError
    """
    if keyisset("router", service) and service["router"] not in routers.keys():
        raise KeyError(
            "Routers provided not found in the routers description. Got",
            service["routers"],
            "Expected",
            routers.keys(),
        )
    if keyisset("node", service) and service["node"] not in nodes.keys():
        raise KeyError(
            "Nodes provided not found in nodes defined. Got",
            service["node"],
            "Expected one of",
            nodes.keys(),
        )


class MeshService(object):
    """
    Class to represent a mesh Virtual Service.
    """

    def __init__(self, name, definition, routers, nodes, mesh):
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
            nodes[self.definition["node"]]
            if keyisset("node", self.definition)
            else None
        )
        service_router = (
            routers[self.definition["router"]]
            if keyisset("router", self.definition)
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
            VirtualServiceName=Sub(f"{name}.${{{PRIVATE_DNS_ZONE_NAME.title}}}"),
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

    def add_dns_entries(self, template):
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
            NamespaceId=Ref(PRIVATE_DNS_ZONE_ID),
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
