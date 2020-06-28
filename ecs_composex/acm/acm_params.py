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

Parameters specific to AWS ACM

"""

from troposphere import Parameter

RES_KEY = "x-acm"

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
