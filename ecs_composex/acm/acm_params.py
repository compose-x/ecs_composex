#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Parameters specific to AWS ACM
"""

from os import path

from troposphere import Parameter

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = f"{path.basename(path.dirname(path.abspath(__file__)))}"
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

VALIDATION_DOMAIN_NAME_T = "ValidationDomainName"
VALIDATION_DOMAIN_NAME = Parameter(
    VALIDATION_DOMAIN_NAME_T,
    Type="String",
    Default="none",
    AllowedPattern=r"(^none$|^(\*\.)?(((?!-)[A-Za-z0-9-]{0,62}[A-Za-z0-9])\.)+((?!-)[A-Za-z0-9-]{1,62}[A-Za-z0-9])$)",
)

VALIDATION_DOMAIN_ZONE_ID_T = "ValidationZoneId"
VALIDATION_DOMAIN_ZONE_ID = Parameter(
    VALIDATION_DOMAIN_ZONE_ID_T,
    Type="String",
    AllowedPattern=r"(none|^Z[A-Z0-9]+$)",
    Default="none",
)

CERT_CN_T = "CertificateCn"
CERT_CN = Parameter(
    CERT_CN_T,
    Type="String",
    AllowedPattern=r"^(\*\.)?(((?!-)[A-Za-z0-9-]{0,62}[A-Za-z0-9])\.)+((?!-)[A-Za-z0-9-]{1,62}[A-Za-z0-9])$",
)

CERT_ALT_NAMES_T = "CerticateAlternativeNames"
CERT_ALT_NAMES = Parameter(
    CERT_ALT_NAMES_T, Type="CommaDelimitedList", Default="<none>"
)

CERT_VALIDATION_METHOD_T = "CertificateValidationMethod"
CERT_VALIDATION_METHOD = Parameter(
    CERT_VALIDATION_METHOD_T,
    Type="String",
    AllowedValues=["DNS", "EMAIL"],
    Default="DNS",
)

CERT_ARN_T = "AcmCertificateArn"
CERT_ARN = Parameter(CERT_ARN_T, Type="String")
