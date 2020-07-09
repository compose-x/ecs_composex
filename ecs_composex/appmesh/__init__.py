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
Main module for AppMesh.

Once all services have been deployed and their VirtualNodes are setup, we deploy the Mesh for it.
"""

from troposphere import Ref, GetAtt
from troposphere import appmesh

from ecs_composex.appmesh import appmesh_params, appmesh_conditions
from ecs_composex.appmesh.appmesh_conditions import add_appmesh_conditions
from ecs_composex.appmesh.appmesh_node import MeshNode
from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.appmesh.appmesh_router import MeshRouter
from ecs_composex.appmesh.appmesh_service import MeshService
from ecs_composex.common import (
    keyisset,
    build_template,
    add_parameters,
    LOG,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.vpc import vpc_params


def initialize_mesh_template():
    """
    Initialize template
    """
    template = build_template(
        "AppMesh Root Template", [MESH_NAME, MESH_OWNER_ID, vpc_params.VPC_DNS_ZONE],
    )
    add_appmesh_conditions(template)
    return template


class Mesh(object):
    """
    Class for AppMesh mesh
    """

    mesh_title = "AppMesh"
    nodes = "nodes"
    routers = "routers"
    services = "services"
    required_keys = [nodes, routers, services]

    def __init__(
        self, mesh_definition, services_root_stack,
    ):
        """
        Method to initialize the Mesh

        :param ecs_composex.ecs.ServicesStack services_root_stack: The services root stack
        """
        self.nodes = {}
        self.routers = {}
        self.services = {}
        self.routes = []
        self.mesh_settings = mesh_definition["Settings"]
        self.mesh_properties = mesh_definition["Properties"]
        self.stack_parameters = {MESH_NAME.title: self.mesh_properties["MeshName"]}
        self.template = services_root_stack.stack_template
        self.stack = None

        for key in self.required_keys:
            if key not in self.mesh_settings.keys():
                raise KeyError(f"Key {key} is missing. Required {self.required_keys}")

        self.appmesh = appmesh.Mesh(
            self.mesh_title,
            Condition=appmesh_conditions.USER_IS_SELF_CON_T,
            MeshName=appmesh_conditions.set_mesh_name(),
            Spec=appmesh.MeshSpec(EgressFilter=appmesh.EgressFilter(Type="DROP_ALL")),
        )
        self.stack_parameters.update(
            {
                appmesh_params.MESH_NAME_T: Ref(appmesh_params.MESH_NAME),
                vpc_params.VPC_DNS_ZONE_T: Ref(vpc_params.VPC_DNS_ZONE),
            }
        )
        nodes_keys = ["name", "protocol", "backends"]
        for node in self.mesh_settings["nodes"]:
            if not set(node.keys()).issubset(nodes_keys):
                raise AttributeError(
                    f"Nodes must have set {nodes_keys}. Got", node.keys()
                )
            if node["name"] not in services_root_stack.stack_template.resources:
                raise AttributeError(
                    f'Node defined {node["name"]} is not defined in services stack',
                    services_root_stack.stack_template.resources,
                )
            LOG.debug(node)
            self.nodes[node["name"]] = MeshNode(
                services_root_stack.stack_template.resources[node["name"]],
                node["protocol"],
                node["backends"] if keyisset("backends", node) else None,
            )
            self.nodes[node["name"]].get_node_param = GetAtt(
                self.nodes[node["name"]].param_name, f"Outputs.VirtualNode"
            )
            self.nodes[node["name"]].get_sg_param = GetAtt(
                self.nodes[node["name"]].param_name,
                f"Outputs.{ecs_params.SERVICE_GROUP_ID_T}",
            )
            self.nodes[node["name"]].stack.Parameters.update(
                {MESH_NAME.title: appmesh_conditions.get_mesh_name(self.appmesh)}
            )
        self.define_routes_and_routers()
        self.define_virtual_services()

    def define_routes_and_routers(self):
        """
        Method to register routers
        """
        for router in self.mesh_settings["routers"]:
            name = router["name"]
            self.routers[name] = MeshRouter(
                router["name"], router, self.appmesh, self.nodes
            )

    def define_virtual_services(self):
        """
        Method to parse the services and map them to nodes and routers.
        """
        for service in self.mesh_settings["services"]:
            name = service["name"]
            self.services[name] = MeshService(
                name, service, self.routers, self.nodes, self.appmesh
            )

    def render_mesh_template(self, services_stack, **kwargs):
        """
        Method to create the AppMesh template stack.

        :param ecs_composex.ecs.ServicesStack services_stack: The services root stack
        """
        if self.appmesh.title not in services_stack.stack_template.resources:
            services_stack.stack_template.add_resource(self.appmesh)
            add_appmesh_conditions(services_stack.stack_template)
            add_parameters(
                services_stack.stack_template,
                [
                    appmesh_params.MESH_OWNER_ID,
                    appmesh_params.MESH_NAME,
                    vpc_params.VPC_DNS_ZONE,
                ],
            )
            services_stack.Parameters.update(
                {
                    vpc_params.VPC_DNS_ZONE_T: GetAtt(
                        "vpc", f"Outputs.{vpc_params.VPC_MAP_DNS_ZONE_T}"
                    )
                }
            )
        for router_name in self.routers:
            router = self.routers[router_name]
            self.template.add_resource(router.router)
            for route in router.routes:
                self.template.add_resource(route)
        for service_name in self.services:
            service = self.services[service_name]
            self.template.add_resource(service.service)
            service.add_dns_entries(self.template)
        for res_name in services_stack.stack_template.resources:
            res = services_stack.stack_template.resources[res_name]
            if issubclass(type(res), ComposeXStack):
                res.DependsOn.append(self.appmesh.title)
        for node_name in self.nodes:
            if self.nodes[node_name].backends:
                self.nodes[node_name].expand_backends(services_stack, self.services)
