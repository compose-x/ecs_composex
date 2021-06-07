#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for DNS parameters
"""

from os import path

from ecs_composex.common.cfn_params import Parameter

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"x-{path.basename(path.dirname(path.abspath(__file__)))}"


ZONES_PATTERN = r"^none$|^ns-[a-z0-9]{6,24}$|^Z[0-9A-Z]+$"

PUBLIC_DNS_ZONE_NAME_T = "PublicDnsZoneName"
PUBLIC_DNS_ZONE_NAME = Parameter(
    PUBLIC_DNS_ZONE_NAME_T, Type="String", Default="none.existant"
)

PUBLIC_DNS_ZONE_ID_T = "PublicDnsZoneId"
PUBLIC_DNS_ZONE_ID = Parameter(
    PUBLIC_DNS_ZONE_ID_T,
    Type="String",
    Default="none",
    AllowedPattern=ZONES_PATTERN,
)

PRIVATE_DNS_ZONE_NAME_T = "PrivateDnsZoneName"
PRIVATE_DNS_ZONE_NAME = Parameter(
    PRIVATE_DNS_ZONE_NAME_T, Type="String", Default="cluster.internal"
)

PRIVATE_DNS_ZONE_ID_T = "PrivateDnsZoneId"
PRIVATE_DNS_ZONE_ID = Parameter(
    PRIVATE_DNS_ZONE_ID_T,
    Type="String",
    Default="none",
    AllowedPattern=ZONES_PATTERN,
)

PRIVATE_NAMESPACE_ID_T = "PrivateNamespaceId"
PRIVATE_NAMESPACE_ID = Parameter(
    PRIVATE_NAMESPACE_ID_T, Type="String", Default="none", AllowedPattern=ZONES_PATTERN
)
