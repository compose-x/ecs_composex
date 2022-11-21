#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.route53.route53_stack import HostedZone

from compose_x_common.compose_x_common import keyisset
from troposphere.route53 import HostedZone as CfnHostedZone

from ecs_composex.common.logging import LOG
from ecs_composex.route53.route53_params import (
    LAST_DOT_RE,
    PUBLIC_DNS_ZONE_ID,
    PUBLIC_DNS_ZONE_NAME,
    ZONES_PATTERN,
)


def lookup_hosted_zone(zone, session, private, zone_id=None) -> dict:
    """
    Describes all zones in account via the session, returns the details about the one zone if found

    :param HostecZone zone:
    :param boto3.session.Session session:
    :param bool private:
    :param str zone_id: The Zone ID
    :return:
    """
    client = session.client("route53")
    try:
        if zone_id:
            if not ZONES_PATTERN.match(zone_id):
                raise ValueError(
                    f"{zone.module.res_key}.{zone.name} - HostedZoneId is not valid. Got",
                    zone_id,
                    "Expected to match",
                    ZONES_PATTERN.pattern,
                )
            zone_r = client.get_hosted_zone(Id=zone_id)["HostedZone"]
        else:
            zones_req = client.list_hosted_zones_by_name(DNSName=zone.zone_name)[
                "HostedZones"
            ]
            zones_r = filter_out_cloudmap_zones(zones_req, zone.zone_name)
            zone_r = client.get_hosted_zone(Id=zones_r["Id"])["HostedZone"]

        if zone_r["Config"]["PrivateZone"] != private:
            raise ValueError(f"The zone {zone.zone_name} is not a private zone.")
        return {
            PUBLIC_DNS_ZONE_ID: zone_r["Id"].split(r"/")[-1],
            PUBLIC_DNS_ZONE_NAME: LAST_DOT_RE.sub("", zone_r["Name"]),
        }
    except client.exceptions.InvalidDomainName:
        LOG.warning(f"Zone {zone.zone_name} is invalid or malformed.")


def filter_out_cloudmap_zones(zones: list[dict], zone_name: str):
    """
    Function to filter out the Hosted Zones linked to CloudMap
    """
    new_zones = []
    for zone in zones:
        if (
            keyisset("LinkedService", zone)
            and keyisset("ServicePrincipal", zone["LinkedService"])
            and zone["LinkedService"]["ServicePrincipal"]
            == "servicediscovery.amazonaws.com"
        ):
            continue
        else:
            new_zones.append(zone)
    if not zone_name.endswith("."):
        zone_name = f"{zone_name}."
    if not new_zones or not new_zones[0]["Name"] == zone_name:
        raise LookupError(
            "The first zone found does not match the DNS zone we are looking for."
            "As per API definition, this means the zone was not found",
            new_zones,
        )
    return new_zones[0]


def resolve_lookup(
    lookup_resources: list[HostedZone],
    settings: ComposeXSettings,
    module: XResourceModule,
) -> None:
    """
    Lookup the ACM certificates in AWS and creates the CFN mappings for them

    :param list[HostedZone] lookup_resources: List of resources to lookup
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param XResourceModule module:
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            ZONES_PATTERN, lookup_hosted_zone, CfnHostedZone.resource_type, ""
        )
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )
        resource.init_outputs()
        resource.generate_outputs()
    LOG.debug(settings.mappings[module.mapping_key])
