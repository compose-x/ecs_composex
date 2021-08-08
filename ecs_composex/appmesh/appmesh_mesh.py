#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Main module for AppMesh.

Once all services have been deployed and their VirtualNodes are setup, we deploy the Mesh for it.
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_STACK_NAME, GetAtt, Ref, appmesh

from ecs_composex.appmesh import appmesh_conditions, appmesh_params, metadata
from ecs_composex.appmesh.appmesh_aws import lookup_mesh_by_name
from ecs_composex.appmesh.appmesh_conditions import add_appmesh_conditions
from ecs_composex.appmesh.appmesh_node import MeshNode
from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.appmesh.appmesh_router import MeshRouter
from ecs_composex.appmesh.appmesh_service import MeshService
from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.resources_import import import_record_properties


class Mesh(object):
    """
    Class for AppMesh mesh
    """

    mesh_title = "ServiceMesh"
    nodes_key = appmesh_params.NODES_KEY
    routers_key = appmesh_params.ROUTERS_KEY
    services_key = appmesh_params.SERVICES_KEY
    required_keys = [nodes_key, routers_key, services_key]

    def __init__(self, mesh_definition, services_root_stack, settings, dns_settings):
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
            if self.mesh_properties:
                props = import_record_properties(self.mesh_properties, appmesh.Mesh)
                props["Metadata"] = metadata
                props["MeshName"] = appmesh_conditions.set_mesh_name()
            else:
                props = {
                    "Spec": appmesh.MeshSpec(
                        EgressFilter=appmesh.EgressFilter(Type="DENY_ALL")
                    ),
                    "MeshName": appmesh_conditions.set_mesh_name(),
                }
            self.appmesh = appmesh.Mesh(
                self.mesh_title,
                template=services_root_stack.stack_template,
                **props,
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
        self.define_nodes(settings, services_root_stack, self.appmesh)
        self.define_routes_and_routers()
        self.define_virtual_services(dns_settings)

    def define_nodes(self, settings, services_root_stack, mesh):
        """
        Method to compile the nodes for the Mesh.

        :param services_root_stack: The services root stack where the services are.
        :type services_root_stack: ecs_composex.ecs.ServicesStack
        :return:
        """
        nodes_keys = [
            appmesh_params.NAME_KEY,
            appmesh_params.PROTOCOL_KEY,
            appmesh_params.BACKENDS_KEY,
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
            self.nodes[family.logical_name] = MeshNode(
                family,
                node[appmesh_params.PROTOCOL_KEY],
                mesh,
                node[appmesh_params.BACKENDS_KEY]
                if keyisset(appmesh_params.BACKENDS_KEY, node)
                else None,
            )
            self.nodes[family.logical_name].get_node_param = GetAtt(
                self.nodes[family.logical_name].param_name,
                "Outputs.VirtualNode",
            )
            self.nodes[family.logical_name].get_sg_param = GetAtt(
                self.nodes[family.logical_name].param_name,
                f"Outputs.{ecs_params.SERVICE_GROUP_ID_T}",
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
                self.appmesh,
                self.nodes,
            )

    def define_virtual_services(self, dns_settings):
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
                self.appmesh,
                dns_settings,
            )

    def render_mesh_template(self, services_stack, settings, dns_settings):
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
        self.process_mesh_components(services_stack, dns_settings)

    def process_mesh_components(self, services_stack, dns_settings):

        for router_name in self.routers:
            router = self.routers[router_name]
            services_stack.stack_template.add_resource(router.router)
            for route in router.routes:
                services_stack.stack_template.add_resource(route)
        for service_name in self.services:
            service = self.services[service_name]
            services_stack.stack_template.add_resource(service.service)
            service.add_dns_entries(services_stack.stack_template, dns_settings)
        for res_name in services_stack.stack_template.resources:
            res = services_stack.stack_template.resources[res_name]
            if issubclass(type(res), ComposeXStack) and isinstance(self.appmesh, Mesh):
                res.add_dependencies(self.appmesh.title)
        for node_name in self.nodes:
            if self.nodes[node_name].backends:
                self.nodes[node_name].expand_backends(services_stack, self.services)
