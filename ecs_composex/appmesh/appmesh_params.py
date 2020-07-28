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
AppMesh parameters
"""

from troposphere import Parameter

RES_KEY = "appmesh"

MESH_NAME_T = "AppMeshName"
MESH_NAME = Parameter(MESH_NAME_T, Type="String", Default="AutoCreate")

MESH_OWNER_ID_T = "MeshOwnerId"
MESH_OWNER_ID = Parameter(MESH_OWNER_ID_T, Type="String", AllowedPattern=r"[0-9]{12}")

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
