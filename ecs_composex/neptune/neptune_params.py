#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.rds.rds_params import (
    DB_ENDPOINT_ADDRESS_T,
    DB_ENDPOINT_PORT_T,
    DB_RO_ENDPOINT_ADDRESS_T,
)

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

DB_CLUSTER_RESOURCES_ARN_T = "DBClusterResources"
DB_CLUSTER_RESOURCES_ARN = Parameter(DB_CLUSTER_RESOURCES_ARN_T, Type="String")

DB_RESOURCE_ID_T = "ClusterResourceId"
DB_RESOURCE_ID = Parameter(
    DB_RESOURCE_ID_T, return_value=DB_RESOURCE_ID_T, Type="String"
)

DB_ENDPOINT = Parameter(DB_ENDPOINT_ADDRESS_T, return_value="Endpoint", Type="String")
DB_READ_ENDPOINT = Parameter(
    DB_RO_ENDPOINT_ADDRESS_T, return_value="ReadEndpoint", Type="String"
)
DB_PORT = Parameter(
    DB_ENDPOINT_PORT_T,
    return_value="Port",
    Type="Number",
    MinValue=1,
    MaxValue=((2 ^ 16) - 1),
)
