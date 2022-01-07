#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for DNS Route53 parameters
"""
import re
from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"x-{path.basename(path.dirname(path.abspath(__file__)))}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)
TAGGING_API_ID = "route53"

ZONES_PATTERN = re.compile(r"^Z[0-9A-Z]+$")
LAST_DOT_RE = re.compile(r"(\.{1}$)")

PUBLIC_DNS_ZONE_ID_T = "PublicDnsZoneId"
PUBLIC_DNS_ZONE_ID = Parameter(
    PUBLIC_DNS_ZONE_ID_T,
    Type="String",
    AllowedPattern=ZONES_PATTERN.pattern,
)

PUBLIC_DNS_ZONE_ARN_T = "PublicDnsZoneArn"
PUBLIC_DNS_ZONE_ARN = Parameter(
    PUBLIC_DNS_ZONE_ARN_T,
    Type="String",
)
