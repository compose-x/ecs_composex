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

from troposphere import Ref, GetAtt, AWS_ACCOUNT_ID, AWS_STACK_NAME
from troposphere import appmesh

from ecs_composex.appmesh import appmesh_params, appmesh_conditions
from ecs_composex.appmesh import metadata
from ecs_composex.appmesh.appmesh_aws import lookup_mesh_by_name
from ecs_composex.appmesh.appmesh_conditions import add_appmesh_conditions
from ecs_composex.appmesh.appmesh_node import MeshNode
from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.appmesh.appmesh_router import MeshRouter
from ecs_composex.appmesh.appmesh_service import MeshService
from ecs_composex.common import (
    keyisset,
    add_parameters,
    LOG,
)
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_template import get_service_family_name


class Mesh(object):
    """
    Class for AppMesh mesh
    """

    mesh_title = "ServiceMesh"
    nodes_key = "nodes"
    routers_key = "routers"
    services_key = "services"
    required_keys = [nodes_key, routers_key, services_key]

    def __init__(
        self, mesh_definition, services_families, services_root_stack, settings
    ):
        """
        Method to initialize the Mesh

        :param services_root_stack: The services root stack
        :type services_root_stack: ecs_composex.ecs.ServicesStack
        """
        self.nodes = {}
        self.routers = {}
        self.services = {}
        self.routes = []
        self.mesh_settings = mesh_definition["Settings"]
        self.mesh_properties = mesh_definition["Properties"]
        self.stack_parameters = {MESH_NAME.title: Ref(ROOT_STACK_NAME)}
        self.stack = None
        self.appmesh = Ref(MESH_NAME)
        add_parameters(
            services_root_stack.stack_template,
            [appmesh_params.MESH_OWNER_ID, appmesh_params.MESH_NAME],
        )
        appmesh_conditions.add_appmesh_conditions(services_root_stack.stack_template)
        if keyisset("MeshName", self.mesh_properties):
            self.mesh_name = self.mesh_properties["MeshName"]
        else:
            self.mesh_name = MESH_NAME.Default

        mesh_info = lookup_mesh_by_name(
            session=settings.session,
            mesh_name=self.mesh_name,
            mesh_owner=str(self.mesh_properties["MeshOwner"])
            if keyisset("MeshOwner", self.mesh_properties)
            else None,
        )
        if mesh_info:
            services_root_stack.Parameters.update(
                {
                    appmesh_params.MESH_NAME_T: mesh_info[MESH_NAME.title],
                    appmesh_params.MESH_OWNER_ID_T: mesh_info[MESH_OWNER_ID.title],
                }
            )
        else:
            self.mesh_name = MESH_NAME.Default
            allowed_values = ["ALLOW_ALL", "DROP_ALL"]
            egress_type = "DROP_ALL"
            if (
                keyisset("EgressFilter", self.mesh_properties)
                and self.mesh_properties["EgressFilter"] in allowed_values
            ):
                egress_type = self.mesh_properties["EgressFilter"]
            elif (
                keyisset("EgressFilter", self.mesh_properties)
                and self.mesh_properties["EgressFilter"] not in allowed_values
            ):
                LOG.warning(
                    f"Invalid EgressFilter value {self.mesh_properties['EgressFilter']}."
                    f" Allowed values: {allowed_values} "
                    "Setting to default: DROP_ALL"
                )
            self.appmesh = appmesh.Mesh(
                self.mesh_title,
                template=services_root_stack.stack_template,
                MeshName=appmesh_conditions.set_mesh_name(),
                Spec=appmesh.MeshSpec(
                    EgressFilter=appmesh.EgressFilter(Type=egress_type)
                ),
                Metadata=metadata,
            )
            services_root_stack.Parameters.update(
                {
                    appmesh_params.MESH_NAME_T: Ref(AWS_STACK_NAME),
                    appmesh_params.MESH_OWNER_ID_T: Ref(AWS_ACCOUNT_ID),
                }
            )
        for key in self.required_keys:
            if key not in self.mesh_settings.keys():
                raise KeyError(f"Key {key} is missing. Required {self.required_keys}")
        self.define_nodes(services_families, services_root_stack)
        self.define_routes_and_routers()
        self.define_virtual_services()

    def define_nodes(self, services_families, services_root_stack):
        """
        Method to compile the nodes for the Mesh.

        :param services_root_stack: The services root stack where the services are.
        :type services_root_stack: ecs_composex.ecs.ServicesStack
        :return:
        """
        nodes_keys = ["name", "protocol", "backends"]
        for node in self.mesh_settings["nodes"]:
            if not set(node.keys()).issubset(nodes_keys):
                raise AttributeError(
                    f"Nodes must have set {nodes_keys}. Got", node.keys()
                )
            service_family = get_service_family_name(services_families, node["name"])
            LOG.debug(service_family)
            if service_family not in services_root_stack.stack_template.resources:
                raise AttributeError(
                    f"Node defined {service_family} is not defined in services stack",
                    services_root_stack.stack_template.resources,
                )
            LOG.debug(node)
            self.nodes[service_family] = MeshNode(
                services_root_stack.stack_template.resources[service_family],
                node["protocol"],
                node["backends"] if keyisset("backends", node) else None,
            )
            self.nodes[service_family].get_node_param = GetAtt(
                self.nodes[service_family].param_name, "Outputs.VirtualNode"
            )
            self.nodes[service_family].get_sg_param = GetAtt(
                self.nodes[service_family].param_name,
                f"Outputs.{ecs_params.SERVICE_GROUP_ID_T}",
            )

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

    def render_mesh_template(self, services_stack):
        """
        Method to create the AppMesh template stack.

        :param ecs_composex.ecs.ServicesStack services_stack: The services root stack
        """
        if (
            isinstance(self.appmesh, Mesh)
            and self.appmesh.title not in services_stack.stack_template.resources
        ):
            services_stack.stack_template.add_resource(self.appmesh)
            add_appmesh_conditions(services_stack.stack_template)
        self.process_mesh_components(services_stack)

    def process_mesh_components(self, services_stack):

        for router_name in self.routers:
            router = self.routers[router_name]
            services_stack.stack_template.add_resource(router.router)
            for route in router.routes:
                services_stack.stack_template.add_resource(route)
        for service_name in self.services:
            service = self.services[service_name]
            services_stack.stack_template.add_resource(service.service)
            service.add_dns_entries(services_stack.stack_template)
        for res_name in services_stack.stack_template.resources:
            res = services_stack.stack_template.resources[res_name]
            if issubclass(type(res), ComposeXStack) and isinstance(self.appmesh, Mesh):
                res.add_dependencies(self.appmesh.title)
        for node_name in self.nodes:
            if self.nodes[node_name].backends:
                self.nodes[node_name].expand_backends(services_stack, self.services)
