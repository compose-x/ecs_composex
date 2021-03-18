#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
AppMesh parameters
"""

from troposphere import Parameter

RES_KEY = "appmesh"

LISTENER_KEY = "Listener"
PROTOCOL_KEY = "Protocol"
ROUTES_KEY = "Routes"
MATCH_KEY = "Match"
PORT_KEY = "Port"
NODE_KEY = "Node"
NAME_KEY = "Name"
PREFIX_KEY = "Prefix"
METHOD_KEY = "Method"
SCHEME_KEY = "Scheme"
BACKENDS_KEY = "Backends"
SERVICES_KEY = "Services"
NODES_KEY = "Nodes"
ROUTER_KEY = "Router"
ROUTERS_KEY = "Routers"

MESH_NAME_T = "AppMeshName"
MESH_NAME = Parameter(MESH_NAME_T, Type="String", Default="AutoCreate")

MESH_OWNER_ID_T = "MeshOwnerId"
MESH_OWNER_ID = Parameter(
    MESH_OWNER_ID_T, Type="String", AllowedPattern=r"self|^[0-9]{12}$", Default="self"
)

USE_APP_MESH_T = "UseAppMesh"
USE_APP_MESH = Parameter(
    USE_APP_MESH_T, Type="String", AllowedValues=["True", "False"], Default="True"
)

ENVOY_IMAGE_URL_T = "EnvoyLatestImageUrl"
ENVOY_IMAGE_URL = Parameter(
    ENVOY_IMAGE_URL_T,
    Type="AWS::SSM::Parameter::Value<String>",
    Default="/aws/service/appmesh/envoy",
)
