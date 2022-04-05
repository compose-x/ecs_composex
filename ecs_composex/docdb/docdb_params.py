# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.rds.rds_params import (
    DB_ENDPOINT_ADDRESS_T,
    DB_ENDPOINT_PORT_T,
    DB_RO_ENDPOINT_ADDRESS_T,
)

DOCDB_NAME_T = "DBClusterName"
DOCDB_ID_T = "ClusterResourceId"

DOCDB_NAME = Parameter(DOCDB_NAME_T, Type="String")
DOCDB_ID = Parameter(DOCDB_ID_T, return_value="ClusterResourceId", Type="String")
DOCDBC_ENDPOINT = Parameter(
    DB_ENDPOINT_ADDRESS_T, return_value="Endpoint", Type="String"
)
DOCDBC_READ_ENDPOINT = Parameter(
    DB_RO_ENDPOINT_ADDRESS_T, return_value="ReadEndpoint", Type="String"
)
DOCDB_PORT = Parameter(
    DB_ENDPOINT_PORT_T,
    return_value="Port",
    Type="Number",
    MinValue=1,
    Default="27017",
    MaxValue=((2 ^ 16) - 1),
)
