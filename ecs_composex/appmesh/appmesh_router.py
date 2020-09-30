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
Module to manage Routers specifically.
"""
from troposphere import AWS_NO_VALUE
from troposphere import Sub, Ref, GetAtt
from troposphere import appmesh

from ecs_composex.appmesh import appmesh_conditions
from ecs_composex.common import NONALPHANUM, keyisset, LOG


def define_http_route(route_match, route_nodes):
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
                    VirtualNode=node.get_node_param,
                    Weight=node.weight,
                )
                for node in route_nodes
            ]
        ),
    )
    return route


def define_route_name(route_match):
    """
    Function to create the route name for an AppMesh Router.

    :param dict route_match: The route argument.
    :return:
    """
    prefix = "prefix"
    method = "method"
    scheme = "scheme"

    allowed_methods = [
        "GET",
        "CONNECT",
        "DELETE",
        "HEAD",
        "OPTIONS",
        "PATCH",
        "POST",
        "PUT",
        "TRACE",
    ]
    allowed_schemes = ["http", "https"]

    prefix_suffix = ""
    method_suffix = ""
    scheme_suffix = ""

    if keyisset(prefix, route_match) and not route_match[prefix].startswith("/"):
        raise ValueError(f"Route {route_match[prefix]} does not start with /")
    elif keyisset(prefix, route_match) and route_match[prefix].startswith("/"):
        prefix_suffix = "".join([key.title() for key in route_match[prefix].split("/")])

    if keyisset(method, route_match) and route_match[method] in allowed_methods:
        method_suffix = route_match[method].title()
    elif keyisset(method, route_match) and route_match[method] not in allowed_methods:
        raise ValueError("Match method must be one of", allowed_methods)
    if keyisset(scheme, route_match) and route_match[scheme] in allowed_schemes:
        method_suffix = route_match[scheme].title()
    elif keyisset(scheme, route_match) and route_match[scheme] not in allowed_schemes:
        raise ValueError("Match scheme must be one of", allowed_schemes)
    return f"{scheme_suffix}{method_suffix}{prefix_suffix}"


class MeshRouter(object):
    """
    Defines a router.
    """

    tcp_routes_keys = ["nodes"]
    http_routes_keys = ["match", "nodes"]

    def __init__(self, name, definition, mesh, nodes):
        """
        Method to initialize the router

        :param str name:
        :param dict definition:
        :param troposphere.appmesh.Mesh mesh: The mesh to add the router to.
        :param dict nodes: list of nodes defined in the mesh.
        """

        self.title = NONALPHANUM.sub("", name)
        self.definition = definition
        self.validate_definition()
        self.mesh = mesh
        self.port = self.definition["listener"]["port"]
        self.protocol = self.definition["listener"]["protocol"]
        self.raw_routes = self.definition["routes"]
        self.routes = []
        self.nodes = []
        self.router = appmesh.VirtualRouter(
            f"VirtualRouter{self.title}",
            MeshName=appmesh_conditions.get_mesh_name(mesh),
            MeshOwner=appmesh_conditions.set_mesh_owner_id(),
            VirtualRouterName=Sub(f"{self.title}-vr-${{AWS::StackName}}"),
            Spec=appmesh.VirtualRouterSpec(
                Listeners=[
                    appmesh.VirtualRouterListener(
                        PortMapping=appmesh.PortMapping(
                            Port=self.port, Protocol=self.protocol
                        )
                    )
                ]
            ),
        )
        self.add_routes(nodes)

    def validate_definition(self):
        """
        Method to validate the router definition
        """
        if not keyisset("routes", self.definition):
            raise KeyError(f"No routes defined for the router {self.title}")
        routes = self.definition["routes"]
        if not keyisset("listener", self.definition):
            raise KeyError(f"No listener configured for router {self.title}")
        listener = self.definition["listener"]
        if not keyisset("port", listener) or not keyisset("protocol", listener):
            raise KeyError("Listener for router requires port and protocol")
        if not listener["protocol"] in routes.keys():
            raise ValueError(
                f"The virtual router is configured for {listener['protocol']} but no such route configured"
            )

    def handle_http_route(self, routes, router, nodes, http2=False):
        """
        Function to create a HTTP or HTTP/2 route

        :param list routes: routes of HTTP or HTTP2 protocol
        :param troposphere.appmesh.VirtualRouter router: The virtual router to attach the route to.
        :param dict nodes: list of nodes.
        :param http2: whether it is http2
        :return:
        """
        for route in routes:
            if not all(key in ["match", "nodes"] for key in route.keys()):
                raise AttributeError(
                    "Each route must have match and nodes. Got", route.keys()
                )
            route_nodes = []
            for node in route["nodes"]:
                if node["name"] in nodes.keys():
                    route_nodes.append(nodes[node["name"]])
                else:
                    raise ValueError(
                        f'node {node["name"]} is not defined as a virtual node.'
                    )
            route_match = route["match"]
            route = define_http_route(route_match, route_nodes)
            self.nodes += [node for node in route_nodes]
            route_name = define_route_name(route_match)
            protocol = "HttpRoute"
            if http2:
                protocol = "Http2Route"
            self.routes.append(
                appmesh.Route(
                    f"{router.title}{route_name}",
                    MeshName=GetAtt(router, "MeshName"),
                    MeshOwner=GetAtt(router, "MeshOwner"),
                    VirtualRouterName=GetAtt(router, "VirtualRouterName"),
                    RouteName=route_name,
                    Spec=appmesh.RouteSpec(**{protocol: route}),
                )
            )

    def handle_tcp_route(self, routes, router, nodes):
        """
        Function to create the TCP routes for the router

        :param list routes: routes of TCP protocol
        :param troposphere.appmesh.VirtualRouter router: The virtual router to attach the route to.
        :param dict nodes: Nodes in the mesh
        """
        for route in routes:
            if not all(key in ["nodes"] for key in route.keys()):
                raise AttributeError("Each route must have nodes. Got", route.keys())
            route_nodes = []
            for node in route["nodes"]:
                if node["name"] in nodes.keys():
                    route_nodes.append(nodes[node["name"]])
                else:
                    raise ValueError(
                        f'node {node["name"]} is not defined as a virtual node.'
                    )
            route = appmesh.TcpRoute(
                Timeout=appmesh.TcpTimeout(Idle=appmesh.Duration(Unit="ms", Value=1))
                if keyisset("timeout", route)
                else Ref(AWS_NO_VALUE),
                Action=appmesh.TcpRouteAction(
                    WeightedTargets=[
                        appmesh.WeightedTarget(
                            VirtualNode=node.get_node_param,
                            Weight=node.weight,
                        )
                        for node in route_nodes
                    ]
                ),
            )
            protocol = "TcpRoute"
            self.routes.append(
                appmesh.Route(
                    f"{router.title}{protocol}",
                    MeshName=GetAtt(router, "MeshName"),
                    MeshOwner=GetAtt(router, "MeshOwner"),
                    VirtualRouterName=GetAtt(router, "VirtualRouterName"),
                    RouteName=Sub(f"${{AWS::StackName}}{protocol}"),
                    Spec=appmesh.RouteSpec(**{protocol: route}),
                )
            )

    def add_routes(self, nodes):
        """
        Method to register routers
        """
        for route_protocol in self.raw_routes.keys():
            if route_protocol != self.protocol:
                raise ValueError(
                    f"he virtual router is configured for {self.protocol} "
                    f"but a route for protocol {route_protocol} has been found. This is not supported."
                )

            if route_protocol == "http" or route_protocol == "http2":
                self.handle_http_route(
                    self.raw_routes[route_protocol],
                    self.router,
                    nodes,
                    eval('route_protocol == "http2"'),
                )
            elif route_protocol == "tcp":
                self.handle_tcp_route(
                    self.raw_routes[route_protocol], self.router, nodes
                )
            elif route_protocol == "grcp":
                LOG.warn("gRPC is not yet supported. Sorry.")
