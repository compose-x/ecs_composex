#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

import re
from ecs_composex.dns.dns_params import ZONES_PATTERN
from ecs_composex.common import LOG, keyisset


LAST_DOT_RE = re.compile(r"(\.{1}$)")


def validate_zone_id_input(zone_id):
    """
    Function to validate the ZoneID is conform to expectations

    :param str zone_id:
    :return: True/False
    :rtype: str
    """
    zones_re = re.compile(ZONES_PATTERN)
    zones_groups = zones_re.findall(zone_id)
    if not zones_groups:
        raise ValueError("ZoneID is not valid. Got", zone_id, "Expected", ZONES_PATTERN)
    return zones_groups[0]


def get_all_dns_namespaces(session, namespaces=None, next_token=None):
    """
    Function to recursively fetch all namespaces in account

    :param list namespaces:
    :param boto3.session.Session session:
    :param str next_token:
    :return:
    """
    if namespaces is None:
        namespaces = []
    filters = [{"Name": "TYPE", "Values": ["DNS_PRIVATE"], "Condition": "EQ"}]
    client = session.client("servicediscovery")
    if not next_token:
        namespaces_r = client.list_namespaces(Filters=filters)
    else:
        namespaces_r = client.list_namespaces(Filters=filters, NextToken=next_token)
    namespaces += namespaces_r["Namespaces"]
    if "NextToken" in namespaces_r:
        return get_all_dns_namespaces(session, namespaces, namespaces_r["NextToken"])
    return namespaces


def lookup_service_discovery_namespace(zone, session, private):
    client = session.client("servicediscovery")
    try:
        namespaces = get_all_dns_namespaces(session)
        if zone.name not in [z["Name"] for z in namespaces]:
            raise LookupError("No private namespace found for zone", zone.name)
        the_zone = None
        for l_zone in namespaces:
            if zone.name == l_zone["Name"]:
                the_zone = l_zone
        zone_r = client.get_namespace(Id=the_zone["Id"])
        properties = zone_r["Namespace"]["Properties"]
        if zone_r["Namespace"]["Type"] == "HTTP":
            raise TypeError(
                "Unsupported CloudMap namespace HTTP. "
                "Only DNS namespaces, private or public, are supported"
            )
        return {
            "Route53ID": properties["DnsProperties"]["HostedZoneId"],
            "ZoneTld": LAST_DOT_RE.sub("", properties["HttpProperties"]["HttpName"]),
            "ZoneId": zone_r["Namespace"]["Id"],
        }
    except client.exceptions.NamespaceNotFound:
        LOG.error(f"Namespace not found for {zone.name}")
        raise
    except client.exceptions.InvalidInput:
        LOG.error("Failed to retrieve the zone info")
        raise


def filter_out_cloudmap_zones(zones, zone_name):
    """
    Function to filter out the Hosted Zones linked to CloudMap

    :param list zones:
    :return: The only valid zone
    :rtype: dict
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


def lookup_route53_namespace(zone, session, private):
    client = session.client("route53")
    try:
        zones_req = client.list_hosted_zones_by_name(DNSName=zone.name)["HostedZones"]
        zones_r = filter_out_cloudmap_zones(zones_req, zone.name)
        zone_r = client.get_hosted_zone(Id=zones_r["Id"])["HostedZone"]
        if zone_r["Config"]["PrivateZone"] != private:
            raise ValueError(f"The zone {zone.name} is not a private zone.")
        return {
            "ZoneId": zone_r["Id"].split(r"/")[-1],
            "ZoneTld": LAST_DOT_RE.sub("", zone_r["Name"]),
        }
    except client.exceptions.InvalidDomainName:
        LOG.warning(f"Zone {zone.name} is invalid or malformed.")


def lookup_namespace(zone, session):
    """
    Function to find the namespace infos

    :param ecs_composex.dns.DnsZone zone:
    :param boto3.session.Session session: boto3 session to make API call
    :return:
    """
    zone_info = None
    if zone.key == "PrivateNamespace":
        zone_info = lookup_service_discovery_namespace(zone, session, private=True)
    elif zone.key == "PublicZone":
        zone_info = lookup_route53_namespace(zone, session, private=False)
    return zone_info
