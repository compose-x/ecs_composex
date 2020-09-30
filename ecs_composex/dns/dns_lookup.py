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

import re
from ecs_composex.dns.dns_params import ZONES_PATTERN
from ecs_composex.common import LOG


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


def lookup_service_discovery_namespace(zone_id, session, private):
    client = session.client("servicediscovery")
    try:
        zone_r = client.get_namespace(Id=zone_id)
        properties = zone_r["Namespace"]["Properties"]
        if zone_r["Namespace"]["Type"] == "HTTP":
            raise TypeError(
                "Unsupported CloudMap namespace HTTP. "
                "Only DNS namespaces, private or public, are supported"
            )
        return {
            "ZoneId": properties["DnsProperties"]["HostedZoneId"],
            "ZoneTld": LAST_DOT_RE.sub("", properties["HttpProperties"]["HttpName"]),
            "NamespaceId": zone_r["Namespace"]["Id"],
        }
    except client.exceptions.NamespaceNotFound:
        LOG.error(f"Namespace ID {zone_id} not found")
        raise


def lookup_route53_namespace(zone_id, session, private):
    client = session.client("route53")
    try:
        zone_r = client.get_hosted_zone(Id=zone_id)["HostedZone"]
        if zone_r["Config"]["PrivateZone"] != private:
            raise ValueError(f"The zone {zone_id} is not a private zone.")
        return {
            "ZoneId": zone_r["Id"].split(r"/")[-1],
            "ZoneTld": LAST_DOT_RE.sub("", zone_r["Name"]),
        }
    except client.exceptions.NoSuchHostedZone:
        LOG.warning(f"Zone {zone_id} not found in your account.")


def lookup_namespace(zone_id, session, private=False):
    """
    Function to find the namespace infos

    :param str zone_id:
    :param boto3.session.Session session: boto3 session to make API call
    :param bool private: Whether this zone is private or not
    :return:
    """
    zone_id = validate_zone_id_input(zone_id)
    zone_info = None
    if zone_id == "none":
        raise ValueError("Value is none. This can't work.")
    if zone_id.startswith("ns-"):
        zone_info = lookup_service_discovery_namespace(zone_id, session, private)
    elif zone_id.startswith("Z"):
        zone_info = lookup_route53_namespace(zone_id, session, private)
    return zone_info
