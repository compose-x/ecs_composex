# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for AWS CloudMap
"""
import re
from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"x-{path.basename(path.dirname(path.abspath(__file__)))}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)
TAGGING_API_ID = "route53"

ZONES_PATTERN = re.compile(r"^ns[0-9a-zA-Z]+$")
LAST_DOT_RE = re.compile(r"(\.{1}$)")

PRIVATE_DNS_ZONE_NAME_T = "PrivateDnsZoneName"
PRIVATE_DNS_ZONE_NAME = Parameter(
    PRIVATE_DNS_ZONE_NAME_T, Type="String", Default="cluster.internal"
)

PRIVATE_DNS_ZONE_ID_T = "PrivateDnsZoneId"
PRIVATE_DNS_ZONE_ID = Parameter(
    PRIVATE_DNS_ZONE_ID_T,
    Type="String",
    Default="none",
    AllowedPattern=ZONES_PATTERN.pattern,
)

PRIVATE_NAMESPACE_ID_T = "PrivateNamespaceId"
PRIVATE_NAMESPACE_ID = Parameter(
    PRIVATE_NAMESPACE_ID_T,
    Type="String",
    Default="none",
    AllowedPattern=ZONES_PATTERN.pattern,
)
