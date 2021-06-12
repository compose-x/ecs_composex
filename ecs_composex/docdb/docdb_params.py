#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY
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
