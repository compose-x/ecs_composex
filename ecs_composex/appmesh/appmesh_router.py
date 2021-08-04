#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage Routers specifically.
"""
from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, GetAtt, Ref, Sub, appmesh

from ecs_composex.appmesh import appmesh_conditions
from ecs_composex.appmesh.appmesh_params import (
    LISTENER_KEY,
    MATCH_KEY,
    METHOD_KEY,
    NAME_KEY,
    NODES_KEY,
    PORT_KEY,
    PREFIX_KEY,
    PROTOCOL_KEY,
    ROUTES_KEY,
    SCHEME_KEY,
)
from ecs_composex.common import LOG, NONALPHANUM


def define_http_route(route_match, route_nodes):
    route = appmesh.HttpRoute(
        Match=appmesh.HttpRouteMatch(
            Prefix=route_match[PREFIX_KEY]
            if keyisset(PREFIX_KEY, route_match)
            else Ref(AWS_NO_VALUE),
            Scheme=route_match[SCHEME_KEY]
            if keyisset(SCHEME_KEY, route_match)
            else Ref(AWS_NO_VALUE),
            Method=route_match[METHOD_KEY]
            if keyisset(METHOD_KEY, route_match)
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
    prefix = PREFIX_KEY
    method = METHOD_KEY
    scheme = SCHEME_KEY

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
    allowed_schemes = ["Http", "Https"]

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

    tcp_routes_keys = [NODES_KEY]
    http_routes_keys = [MATCH_KEY, NODES_KEY]

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
        self.port = self.definition[LISTENER_KEY][PORT_KEY]
        self.protocol = self.definition[LISTENER_KEY][PROTOCOL_KEY]
        self.raw_routes = self.definition[ROUTES_KEY]
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
        if not keyisset(ROUTES_KEY, self.definition):
            raise KeyError(f"No routes defined for the router {self.title}")
        routes = self.definition[ROUTES_KEY]
        if not keyisset(LISTENER_KEY, self.definition):
            raise KeyError(f"No listener configured for router {self.title}")
        listener = self.definition[LISTENER_KEY]
        if not keyisset(PORT_KEY, listener) or not keyisset(PROTOCOL_KEY, listener):
            raise KeyError("Listener for router requires Port and Protocol")
        if not listener[PROTOCOL_KEY] in routes.keys():
            raise ValueError(
                f"The virtual router is configured for {listener[PROTOCOL_KEY]} but no such route configured"
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
            if not all(key in [MATCH_KEY, NODES_KEY] for key in route.keys()):
                raise AttributeError(
                    "Each route must have match and nodes. Got", route.keys()
                )
            route_nodes = []
            for node in route[NODES_KEY]:
                if node[NAME_KEY] in nodes.keys():
                    route_nodes.append(nodes[node[NAME_KEY]])
                else:
                    raise ValueError(
                        f"node {node[NAME_KEY]} is not defined as a virtual node."
                    )
            route_match = route[MATCH_KEY]
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
            if not all(key in [NODES_KEY] for key in route.keys()):
                raise AttributeError("Each route must have nodes. Got", route.keys())
            route_nodes = []
            for node in route[NODES_KEY]:
                if node[NAME_KEY] in nodes.keys():
                    route_nodes.append(nodes[node[NAME_KEY]])
                else:
                    raise ValueError(
                        f"node {node[NAME_KEY]} is not defined as a virtual node."
                    )
            route = appmesh.TcpRoute(
                Timeout=appmesh.TcpTimeout(Idle=appmesh.Duration(Unit="ms", Value=1))
                if keyisset("Timeout", route)
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

            if route_protocol == "Http" or route_protocol == "Http2":
                self.handle_http_route(
                    self.raw_routes[route_protocol],
                    self.router,
                    nodes,
                    eval('route_protocol == "Http2"'),
                )
            elif route_protocol == "Tcp":
                self.handle_tcp_route(
                    self.raw_routes[route_protocol], self.router, nodes
                )
            elif route_protocol == "gRPC":
                LOG.warning("gRPC is not yet supported. Sorry.")
