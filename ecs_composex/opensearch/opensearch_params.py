#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
OpenSearch parameters
"""
import re

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

OS_DOMAIN_ID_T = "DomainId"
OS_DOMAIN_ID = Parameter(OS_DOMAIN_ID_T, Type="String")

OS_DOMAIN_ARN_T = "DomainArn"
OS_DOMAIN_ARN = Parameter(OS_DOMAIN_ARN_T, return_value="Arn", Type="String")

OS_DOMAIN_ENDPOINT_T = "DomainEndpoint"
OS_DOMAIN_ENDPOINT = Parameter(
    OS_DOMAIN_ENDPOINT_T, return_value="DomainEndpoint", Type="String"
)

OS_DOMAIN_SG_T = "DomainSg"
OS_DOMAIN_SG = Parameter(OS_DOMAIN_SG_T, return_value="GroupId", Type=SG_ID_TYPE)

OS_DOMAIN_PORT_T = "DomainPort"
OS_DOMAIN_PORT = Parameter(
    OS_DOMAIN_PORT_T, Type="Number", Default=443, MinValue=0, MaxValue=(pow(2, 16) - 1)
)

OS_DOMAIN_ARN_RE = re.compile(
    r"(?:^arn:aws(?:-[a-z]+)?:es:[\w-]+:[0-9]{12}:domain/)(?P<domain>[\S]+)$"
)
