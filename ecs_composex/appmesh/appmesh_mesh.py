# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module for AppMesh.

Once all services have been deployed and their VirtualNodes are setup, we deploy the Mesh for it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_ACCOUNT_ID, AWS_STACK_NAME, GetAtt, Output, Ref, appmesh

from ecs_composex.appmesh import appmesh_conditions, appmesh_params, metadata
from ecs_composex.appmesh.appmesh_aws import lookup_mesh_by_name
from ecs_composex.appmesh.appmesh_conditions import add_appmesh_conditions
from ecs_composex.appmesh.appmesh_node import MeshNode
from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.appmesh.appmesh_router import MeshRouter
from ecs_composex.appmesh.appmesh_service import MeshService
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_resource,
    build_template,
)
from ecs_composex.resources_import import import_record_properties


class Mesh:
    """
    Class for AppMesh mesh
    """

    mesh_title = "ServiceMesh"
    nodes_key = appmesh_params.NODES_KEY
    routers_key = appmesh_params.ROUTERS_KEY
    services_key = appmesh_params.SERVICES_KEY
    required_keys = [nodes_key, routers_key, services_key]

    def __init__(
        self,
        mesh_definition: dict,
        root_stack: ComposeXStack,
        settings: ComposeXSettings,
    ):
        """
        Method to initialize the Mesh

        :param root_stack: The services root stack
        :type root_stack: ecs_composex.ecs.ServicesStack
        """
        self.nodes = {}
        self.routers = {}
        self.services = {}
        self.routes = []
        self.mesh_settings = mesh_definition["Settings"]
        self.mesh_properties = set_else_none(
            "Properties", mesh_definition, alt_value={}
        )
        self.lookup = set_else_none("Lookup", mesh_definition)
        stack_parameters = {MESH_NAME.title: Ref(ROOT_STACK_NAME)}
        template = build_template(
            "AppMesh", [appmesh_params.MESH_OWNER_ID, appmesh_params.MESH_NAME]
        )
        self.stack = ComposeXStack(
            "appmesh", stack_template=template, stack_parameters=stack_parameters
        )
        self.appmesh = Ref(MESH_NAME)
        add_resource(settings.root_stack.stack_template, self.stack)
        appmesh_conditions.add_appmesh_conditions(self.stack.stack_template)

        if self.lookup:
            mesh_info = lookup_mesh_by_name(
                session=settings.session,
                mesh_name=self.lookup["MeshName"],
                mesh_owner=str(set_else_none("MeshOwner", self.lookup)),
            )
        else:
            mesh_info = None
        if mesh_info:
            self.stack.Parameters.update(
                {
                    appmesh_params.MESH_NAME_T: mesh_info[MESH_NAME.title],
                    appmesh_params.MESH_OWNER_ID_T: mesh_info[MESH_OWNER_ID.title],
                }
            )
            mesh_outputs = [Output(MESH_NAME.title, Value=Ref(MESH_NAME))]
        else:
            if self.mesh_properties:
                props = import_record_properties(self.mesh_properties, appmesh.Mesh)
                props["Metadata"] = metadata
                props["MeshName"] = Ref(MESH_NAME)
            else:
                props = {
                    "Spec": appmesh.MeshSpec(
                        EgressFilter=appmesh.EgressFilter(Type="ALLOW_ALL")
                    ),
                    "MeshName": Ref(MESH_NAME),
                }
            self.appmesh = appmesh.Mesh(
                self.mesh_title,
                **props,
            )
            self.stack.stack_template.add_resource(self.appmesh)
            self.stack.Parameters.update(
                {
                    appmesh_params.MESH_NAME_T: Ref(AWS_STACK_NAME),
                    appmesh_params.MESH_OWNER_ID_T: Ref(AWS_ACCOUNT_ID),
                }
            )
            if self.mesh_properties and keyisset("MeshName", self.mesh_properties):
                self.stack.Parameters.update(
                    {MESH_NAME.title: self.mesh_properties["MeshName"]}
                )
            mesh_outputs = [
                Output(MESH_NAME.title, Value=GetAtt(self.appmesh, "MeshName"))
            ]
        add_outputs(self.stack.stack_template, mesh_outputs)
        for key in self.required_keys:
            if key not in self.mesh_settings.keys():
                raise KeyError(f"Key {key} is missing. Required {self.required_keys}")
        self.define_nodes(settings)
        self.define_routes_and_routers()
        self.define_virtual_services(settings)

    def define_nodes(self, settings: ComposeXSettings) -> None:
        """
        Method to compile the nodes for the Mesh.
        """
        nodes_keys = [
            appmesh_params.NAME_KEY,
            appmesh_params.PROTOCOL_KEY,
            appmesh_params.BACKENDS_KEY,
            "Port",
        ]
        for node in self.mesh_settings[self.nodes_key]:
            if not set(node.keys()).issubset(nodes_keys):
                raise AttributeError(
                    f"Nodes must have set {nodes_keys}. Got", node.keys()
                )
            service_families = [
                settings.families[name]
                for name in settings.families
                if settings.families[name].name == node[appmesh_params.NAME_KEY]
            ]
            if len(service_families) > 1:
                raise LookupError(
                    "More than one family matched for the node.",
                    service_families,
                    node[appmesh_params.NAME_KEY],
                )
            elif not service_families:
                raise LookupError(
                    "No family could be matched for the given node",
                    settings.families,
                    node[appmesh_params.NAME_KEY],
                )
            LOG.debug(node)
            family = service_families[0]
            mesh_node = MeshNode(
                family,
                node[appmesh_params.PROTOCOL_KEY],
                node["Port"],
                self,
                settings,
                node[appmesh_params.BACKENDS_KEY]
                if keyisset(appmesh_params.BACKENDS_KEY, node)
                else None,
            )
            self.nodes[family.logical_name] = mesh_node
            self.nodes[family.logical_name].get_node_param = GetAtt(
                mesh_node.node, "VirtualNodeName"
            )
            self.nodes[family.logical_name].get_sg_param = GetAtt(
                self.nodes[family.logical_name].param_name,
                f"Outputs.{family.logical_name}GroupId",
            )

    def define_routes_and_routers(self):
        """
        Method to register routers
        """
        for router in self.mesh_settings[self.routers_key]:
            name = router[appmesh_params.NAME_KEY]
            self.routers[name] = MeshRouter(
                router[appmesh_params.NAME_KEY],
                router,
                self,
                self.nodes,
            )

    def define_virtual_services(self, settings):
        """
        Method to parse the services and map them to nodes and routers.
        """
        for service in self.mesh_settings[self.services_key]:
            name = service[appmesh_params.NAME_KEY]
            self.services[name] = MeshService(
                name,
                service,
                self.routers,
                self.nodes,
                self,
                settings,
            )

    def render_mesh_template(self, stack: ComposeXStack, settings: ComposeXSettings):
        """
        Method to create the AppMesh template stack.

        :param ComposeXStack stack: The services root stack
        """
        if (
            isinstance(self.appmesh, Mesh)
            and self.appmesh.title not in stack.stack_template.resources
        ):
            stack.stack_template.add_resource(self.appmesh)
            add_appmesh_conditions(stack.stack_template)
        self.process_mesh_components(stack, settings)

    def process_mesh_components(self, services_stack, settings):

        for router_name in self.routers:
            router = self.routers[router_name]
            services_stack.stack_template.add_resource(router.router)
            for route in router.routes:
                services_stack.stack_template.add_resource(route)
        for service_name in self.services:
            service = self.services[service_name]
            services_stack.stack_template.add_resource(service.service)
            service.add_dns_entries(self.stack, settings)
        for res_name in services_stack.stack_template.resources:
            res = services_stack.stack_template.resources[res_name]
            if issubclass(type(res), ComposeXStack) and isinstance(self.appmesh, Mesh):
                res.add_dependencies(self.appmesh.title)
        for node_name in self.nodes:
            if self.nodes[node_name].backends:
                self.nodes[node_name].expand_backends(
                    self, settings.root_stack, self.services
                )
