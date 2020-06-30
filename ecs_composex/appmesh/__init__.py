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

from troposphere import Ref, GetAtt, Sub, Parameter
from troposphere import AWS_ACCOUNT_ID, AWS_NO_VALUE
from troposphere import appmesh

from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.outputs import define_import, formatted_outputs
from ecs_composex.vpc import vpc_params
from ecs_composex.appmesh.appmesh_conditions import add_appmesh_conditions
from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common import keyisset, build_template, add_parameters, NONALPHANUM
from ecs_composex.ecs.ecs_params import SERVICE_NAME
from ecs_composex.vpc.vpc_params import VPC_MAP_ID


def initialize_mesh_template():
    """
    Initialize template
    """
    template = build_template(
        "AppMesh Root Template", [MESH_NAME, MESH_OWNER_ID, vpc_params.VPC_ID]
    )
    add_appmesh_conditions(template)
    return template


class Node(object):
    """
    Class representing an AppMesh Node.
    """

    weight = 1

    def __init__(self, service_stack, protocol):
        """

        :param ecs_composex.ecs.ServiceStack service_stack: the service template
        """
        self.vnode = None
        self.param_name = service_stack.title
        self.get_param = None
        self.stack = service_stack
        self.protocol = protocol
        self.mappings = {}
        self.port_mappings = []
        self.set_port_mappings()
        self.set_listeners_port_mappings()
        self.extend_service_stack()

    def set_port_mappings(self):
        """
        Method to set the port mappings based on the service config ports
        """
        target = "target"
        published = "published"
        for port in self.stack.config.ports:
            if port[target] not in self.mappings.keys():
                self.mappings[port[target]] = {port[published]: port}
            elif (
                port[target] in self.mappings.keys()
                and not port[published] in self.mappings[port[target]]
            ):
                self.mappings[port[target]][port[published]] = port

    def set_listeners_port_mappings(self):
        """
        Method to set the listeners port_mappings
        """
        self.port_mappings = [
            appmesh.PortMapping(Port=port["published"], Protocol=self.protocol)
            for port in self.stack.config.ports
        ]

    def extend_service_stack(self):
        """
        Method to expand the service template with the AppMesh virtual node
        """
        sd_service_name = f"{self.stack.title}DiscoveryService"
        sd_service = self.stack.stack_template.resources[sd_service_name]
        node = appmesh.VirtualNode(
            f"{self.stack.title}VirtualNode",
            MeshName=Ref(MESH_NAME),
            MeshOwner=appmesh_conditions.set_mesh_owner_id(),
            VirtualNodeName=Sub(f"${{{SERVICE_NAME.title}}}${{{ROOT_STACK_NAME_T}}}"),
            Spec=appmesh.VirtualNodeSpec(
                ServiceDiscovery=appmesh.ServiceDiscovery(
                    AWSCloudMap=appmesh.AwsCloudMapServiceDiscovery(
                        NamespaceName=Ref(VPC_MAP_ID), ServiceName=Ref(sd_service)
                    )
                ),
                Listeners=[
                    appmesh.Listener(PortMapping=port_mapping)
                    for port_mapping in self.port_mappings
                ],
            ),
        )
        self.stack.stack_template.add_resource(node)
        add_parameters(
            self.stack.stack_template,
            [appmesh_params.MESH_OWNER_ID, appmesh_params.MESH_NAME],
        )
        add_appmesh_conditions(self.stack.stack_template)
        self.stack.stack_template.add_output(
            formatted_outputs([{"VirtualNode": Ref(node)}], export=True)
        )

    def set_node_weight(self, weight):
        """
        Method to set the weight of the service

        :param int weight:
        :return:
        """
        self.weight = weight


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
        self, mesh_definition, services_root_stack, services_families, **kwargs
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
        self.template = initialize_mesh_template()
        self.stack = None

        for key in self.required_keys:
            if key not in self.mesh_settings.keys():
                raise KeyError(f"Key {key} is missing. Required {self.required_keys}")

        self.mesh = appmesh.Mesh(
            self.mesh_title,
            template=self.template,
            Condition=appmesh_conditions.USER_IS_SELF_CON_T,
            MeshName=Ref(MESH_NAME),
            Spec=appmesh.MeshSpec(EgressFilter=appmesh.EgressFilter(Type="DROP_ALL")),
        )
        for node in self.mesh_settings["nodes"]:
            if not all(key in ["name", "protocol"] for key in node.keys()):
                raise AttributeError(
                    f"Nodes must have set name, protocol. Got", node.keys()
                )
            if node["name"] not in services_root_stack.stack_template.resources:
                raise AttributeError(
                    f'Node definedd {node["name"]} is not defined in services stack',
                    services_root_stack.stack_template.resources,
                )
            self.nodes[node["name"]] = Node(
                services_root_stack.stack_template.resources[node["name"]],
                node["protocol"],
            )
            node_param = self.template.add_parameter(Parameter(
                self.nodes[node["name"]].param_name,
                Type="String",
                Default=node["name"]
            ))
            self.nodes[node["name"]].get_param = node_param
            self.stack_parameters.update(
                {
                    self.nodes[node["name"]].get_param.title: GetAtt(
                        self.nodes[node["name"]].param_name, f"Outputs.VirtualNode"
                    )
                }
            )
        self.init_routers()

    def handle_http_route(self, route_match, nodes, router, http2=False):
        """
        Function to create a HTTP or HTTP/2 route
        :param http2: whether it is http2
        :return:
        """
        route = appmesh.HttpRoute(
            Match=appmesh.HttpRouteMatch(
                Prefix=route_match["prefix"]
                if keyisset("prefix", route_match)
                else Ref(AWS_NO_VALUE),
                Scheme=route_match["scheme"]
                if keyisset("scheme", route_match)
                else Ref(AWS_NO_VALUE),
                Method=route_match["method"]
                if keyisset("method", route_match)
                else Ref(AWS_NO_VALUE),
            ),
            Action=appmesh.HttpRouteAction(
                WeightedTargets=[
                    appmesh.WeightedTarget(
                        VirtualNode=Ref(node.get_param),
                        Weight=node.weight,
                    )
                    for node in nodes
                ]
            ),
        )
        protocol = "HttpRoute"
        if http2:
            protocol = "Http2Route"
        self.routes.append(
            appmesh.Route(
                f"{router.title}{protocol.title()}",
                template=self.template,
                MeshName=Ref(MESH_NAME),
                MeshOwner=appmesh_conditions.set_mesh_owner_id(),
                VirtualRouterName=Ref(router),
                RouteName=Sub(f"${{{router.title}}}${protocol.title()}"),
                Spec=appmesh.RouteSpec(**{protocol: route}),
            )
        )

    def init_routers(self):
        """
        Method to register routers
        :return:
        """
        for router in self.mesh_settings["routers"]:
            name = router["name"]
            router_res_name = NONALPHANUM.sub("", name)
            routes = router["routes"]
            router_listeners = []
            router = appmesh.VirtualRouter(
                f"{router_res_name}VirtualRouter",
                template=self.template,
                MeshName=Ref(MESH_NAME),
                MeshOwner=appmesh_conditions.set_mesh_owner_id(),
                VirtualRouterName=Sub(f"{router_res_name}-vr-${{AWS::StackName}}"),
                Spec=appmesh.VirtualRouterSpec(Listeners=router_listeners),
            )
            self.routers[name] = router_res_name
            for route_protocol in routes.keys():
                route_nodes = []
                for route in routes[route_protocol]:
                    if not all(key in ["match", "nodes"] for key in route.keys()):
                        raise AttributeError(
                            f"Each route must have match and nodes. Got", route.keys()
                        )
                    for node in route["nodes"]:
                        if node["name"] in self.nodes.keys():
                            route_nodes.append(self.nodes[node["name"]])
                        else:
                            raise ValueError(
                                f'node {node["name"]} is not defined as a virtual node.'
                            )
                    for node in route_nodes:
                        for port_map in node.port_mappings:
                            if port_map.Protocol == route_protocol:
                                router_listeners.append(port_map)
                    if route_protocol == "http" or route_protocol == "http2":
                        self.handle_http_route(
                            route["match"],
                            route_nodes,
                            router,
                            eval('route_protocol == "http2"'),
                        )

    def render_mesh_template(self, services_stack, **kwargs):
        """
        Method to create the AppMesh template stack.

        :param ecs_composex.ecs.ServicesStack services_stack: The services root stack
        """
        depends = [res for res in services_stack.stack_template.resources]
        mesh_stack = ComposeXStack(
            self.mesh_title,
            stack_template=self.template,
            Parameters=self.stack_parameters,
            DependsOn=depends,
            **kwargs,
        )
        services_stack.stack_template.add_resource(mesh_stack)
