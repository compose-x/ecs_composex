#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from troposphere import Equals, Not, Ref

from ecs_composex.dns import dns_params

CREATE_PUBLIC_NAMESPACE_CON_T = "CreatePublicServicesNamespaceCondition"
CREATE_PUBLIC_NAMESPACE_CON = Not(
    Equals(
        Ref(dns_params.PUBLIC_DNS_ZONE_NAME),
        dns_params.PUBLIC_DNS_ZONE_NAME.Default,
    )
)
CREATE_PUBLIC_ZONE_CON_T = "CreatePublicServicesZoneCondition"
CREATE_PUBLIC_ZONE_CON = Not(
    Equals(
        Ref(dns_params.PUBLIC_DNS_ZONE_NAME),
        dns_params.PUBLIC_DNS_ZONE_NAME.Default,
    )
)
CREATE_PRIVATE_NAMESPACE_CON_T = "CreatePrivateServicesNamespaceCondition"
CREATE_PRIVATE_NAMESPACE_CON = Equals(
    Ref(dns_params.PRIVATE_DNS_ZONE_ID), dns_params.PRIVATE_DNS_ZONE_ID.Default
)

USE_DEFAULT_ZONE_NAME_CON_T = "UseDefaultPrivateZoneName"
USE_DEFAULT_ZONE_NAME_CON = Equals(
    Ref(dns_params.PRIVATE_DNS_ZONE_NAME),
    dns_params.PRIVATE_DNS_ZONE_NAME.Default,
)

PRIVATE_ZONE_ID_CON_T = "PrivateNamespaceZoneIdCondition"
PRIVATE_ZONE_ID_CON = Not(
    Equals(
        Ref(dns_params.PRIVATE_DNS_ZONE_ID),
        dns_params.PRIVATE_DNS_ZONE_ID.Default,
    )
)

PRIVATE_NAMESPACE_CON_T = "PrivateNamespaceIdCondition"
PRIVATE_NAMESPACE_CON = Not(
    Equals(
        Ref(dns_params.PRIVATE_NAMESPACE_ID),
        dns_params.PRIVATE_NAMESPACE_ID.Default,
    )
)
