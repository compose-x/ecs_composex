#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@compose-x.io>
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

from os import path

from ecs_composex.ecs_composex import X_KEY
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"


DOCDB_NAME_T = "DocDBName"
DOCDB_ID_T = "ClusterResourceId"
DOCDB_ENDPOINT_T = "Endpoint"
DOCDB_READ_ENDPOINT_T = "ReadEndpoint"
DOCDB_PORT_T = "Port"
DOCDB_SG_T = "DocDbSg"
DOCDB_SECRET_T = "DocDbSecret"
DOCDB_SUBNET_GROUP_T = "DocDbSubnetGroup"

DOCDB_NAME = Parameter(DOCDB_NAME_T, Type="String")
DOCDB_ID_T = Parameter(DOCDB_ID_T, return_value="ClusterResourceId", Type="String")
DOCDBC_ENDPOINT = Parameter(DOCDB_ENDPOINT_T, return_value="Endpoint", Type="String")
DOCDBC_READ_ENDPOINT = Parameter(
    DOCDB_READ_ENDPOINT_T, return_value="ReadEndpoint", Type="String"
)
DOCDB_PORT = Parameter(
    DOCDB_PORT_T,
    return_value="Port",
    Type="Number",
    MinValue=1,
    MaxValue=((2 ^ 16) - 1),
)
DOCDB_SG = Parameter(DOCDB_SG_T, return_value="GroupId", Type=SG_ID_TYPE)
DOCDB_SECRET = Parameter(DOCDB_SECRET_T, Type="String")
