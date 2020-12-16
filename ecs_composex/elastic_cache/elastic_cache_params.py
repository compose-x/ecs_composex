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
Parameters for ES Cluster
"""

from os import path
from troposphere import Parameter
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"

CLUSTER_NAME_T = "ClusterName"
CLUSTER_NAME = Parameter(CLUSTER_NAME_T, Type="String")

CLUSTER_SG_T = "GroupId"
CLUSTER_SG = Parameter(CLUSTER_SG_T, Type=SG_ID_TYPE)

CLUSTER_ADDRESS_T = "ClusterAddress"
CLUSTER_ADDRESS = Parameter(
    CLUSTER_ADDRESS_T, Type="String", Description="RedisEndpoint.Address"
)

CLUSTER_PORT_T = "ClusterPort"
CLUSTER_PORT = Parameter(
    CLUSTER_PORT_T,
    Type="Number",
    MinValue=1,
    MaxValue=(pow(2, 16) - 1),
    Description="RedisEndpoint.Port",
)

CLUSTER_CONFIG_ADDRESS_T = "ClusterConfigAddress"
CLUSTER_CONFIG_ADDRESS = Parameter(
    CLUSTER_CONFIG_ADDRESS_T, Type="String", Description="ConfigurationEndpoint.Address"
)

CLUSTER_CONFIG_PORT_T = "ClusterConfigPort"
CLUSTER_CONFIG_PORT = Parameter(
    CLUSTER_CONFIG_PORT_T,
    Type="Number",
    MinValue=1,
    MaxValue=(pow(2, 16) - 1),
    Description="ConfigurationEndpoint.Port",
)
