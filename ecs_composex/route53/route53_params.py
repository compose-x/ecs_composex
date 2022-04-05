# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for DNS Route53 parameters
"""
import re

from ecs_composex.common.cfn_params import Parameter

TAGGING_API_ID = "route53"

ZONES_PATTERN = re.compile(r"^Z[0-9A-Z]+$")
LAST_DOT_RE = re.compile(r"(\.{1}$)")

PUBLIC_DNS_ZONE_ID_T = "PublicDnsZoneId"
PUBLIC_DNS_ZONE_ID = Parameter(
    PUBLIC_DNS_ZONE_ID_T,
    return_value="Id",
    Type="String",
    AllowedPattern=ZONES_PATTERN.pattern,
)

PUBLIC_DNS_ZONE_ARN_T = "PublicDnsZoneArn"
PUBLIC_DNS_ZONE_ARN = Parameter(
    PUBLIC_DNS_ZONE_ARN_T,
    Type="String",
)

PUBLIC_DNS_ZONE_NAME_T = "HostedZoneName"
PUBLIC_DNS_ZONE_NAME = Parameter(PUBLIC_DNS_ZONE_NAME_T, Type="String")


def validate_domain_name(new_record, base_domain):
    """
    Validates that the new alias DNS Name matches the domain basename

    :param str new_record:
    :param str base_domain:
    :raises: ValueError if there is no match
    """
    if not re.findall(base_domain, new_record):
        raise ValueError(
            f"New record {new_record} does not seem to belong to {base_domain}"
        )
