#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.vpc.vpc_stack import XStack as VpcStack
    from boto3.session import Session
    from .cloudmap_stack import PrivateNamespace

from compose_x_common.aws.cloudmap import get_all_dns_namespaces
from compose_x_common.compose_x_common import keyisset
from troposphere.servicediscovery import PrivateDnsNamespace

from ecs_composex.cloudmap.cloudmap_params import (
    LAST_DOT_RE,
    PRIVATE_DNS_ZONE_ID,
    PRIVATE_DNS_ZONE_NAME,
    PRIVATE_NAMESPACE_ID,
    ZONES_PATTERN,
)
from ecs_composex.common.logging import LOG
from ecs_composex.exceptions import ComposeBaseException, IncompatibleOptions


def resolve_lookup(lookup_resources, settings, module: XResourceModule):
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
            ZONES_PATTERN,
            lookup_service_discovery_namespace,
            PrivateDnsNamespace.resource_type,
            "",
        )
        resource.init_outputs()
        resource.generate_cfn_mappings_from_lookup_properties()
        resource.generate_outputs()
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )
    LOG.debug(settings.mappings[module.mapping_key])


def x_cloud_lookup_and_new_vpc(settings: ComposeXSettings, vpc_stack: VpcStack):
    """
    Function to ensure there is no x-cloudmap.Lookup resource and Compose-X is creating a new VPC.
    The Namespace (CloudMap PrivateNamespace) cannot span across multiple VPC

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param vpc_stack: The VPC Stack
    :raises: IncompatibleOptions
    """
    from ecs_composex.cloudmap.cloudmap_stack import PrivateNamespace

    lookup_namespaces = [
        namespace
        for namespace in settings.x_resources
        if isinstance(namespace, PrivateNamespace) and namespace.lookup_properties
    ]
    if lookup_namespaces and not vpc_stack.is_void:
        raise IncompatibleOptions(
            "You cannot have Compose-X Create a new VPC and use x-cloudmap.Lookup."
            " Use x-vpc to re-use the VPC the PrivateNamespace is attached to",
            lookup_namespaces,
        )


def detect_duplicas(x_resources: list[PrivateNamespace]) -> None:
    """
    Function to ensure there is no multiple resources with the same zone name

    :param list[PrivateNamespace] x_resources:
    """

    class DuplicateZoneName(ComposeBaseException):
        pass

    names = [res.zone_name for res in x_resources]
    if len(names) > len(set(names)):
        raise DuplicateZoneName(
            "There is a duplicate of zone names. All names",
            names,
            "unique names",
            set(names),
        )


def lookup_service_discovery_namespace(
    zone: PrivateNamespace, session: Session, ns_id: str = None
) -> dict:
    """
    Function to find and get the PrivateDnsNamespace properties needed by other resources

    :param PrivateNamespace zone:
    :param boto3.session.Session session:
    :param str ns_id:
    :return: The properties we need
    :rtype: dict
    """
    client = session.client("servicediscovery")
    try:
        namespaces = get_all_dns_namespaces(session)
        if zone.zone_name not in [z["Name"] for z in namespaces]:
            raise LookupError(
                "No private namespace found for zone", zone.name, zone.zone_name
            )
        zone_r = None
        if not ns_id:
            for l_zone in namespaces:
                if zone.zone_name == l_zone["Name"]:
                    the_zone = l_zone
                    zone_r = client.get_namespace(Id=the_zone["Id"])
                    break
        else:
            zone_r = client.get_namespace(Id=ns_id)
        if not zone_r:
            raise LookupError(
                f"{zone.module.res_key}.{zone.name} - Failed to lookup {zone.zone_name}"
            )
        properties = zone_r["Namespace"]["Properties"]
        if zone_r["Namespace"]["Type"] == "HTTP":
            raise TypeError(
                "Unsupported CloudMap namespace HTTP. "
                "Only DNS namespaces, private or public, are supported"
            )
        return {
            PRIVATE_DNS_ZONE_ID: properties["DnsProperties"]["HostedZoneId"],
            PRIVATE_DNS_ZONE_NAME: LAST_DOT_RE.sub(
                "", properties["HttpProperties"]["HttpName"]
            ),
            PRIVATE_NAMESPACE_ID: zone_r["Namespace"]["Id"],
        }
    except client.exceptions.NamespaceNotFound:
        LOG.error(f"Namespace not found for {zone.name}")
        raise
    except client.exceptions.InvalidInput:
        LOG.error("Failed to retrieve the zone info")
        raise
