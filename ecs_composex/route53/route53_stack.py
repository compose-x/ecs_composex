#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Main module for ACM
"""

import re
import warnings

from compose_x_common.compose_x_common import keyisset
from troposphere import Ref
from troposphere.route53 import HostedZone as CfnHostedZone

from ecs_composex.acm.acm_params import MAPPINGS_KEY, MOD_KEY, RES_KEY
from ecs_composex.acm.acm_stack import Certificate
from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import (
    AwsEnvironmentResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.elbv2.elbv2_stack import Elbv2

from .route53_acm import handle_acm_records
from .route53_elbv2 import handle_elbv2_records
from .route53_params import (
    LAST_DOT_RE,
    MAPPINGS_KEY,
    MOD_KEY,
    PUBLIC_DNS_ZONE_ID,
    RES_KEY,
    ZONES_PATTERN,
)

LOG = setup_logging()


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
                    f"{RES_KEY}.{zone.name} - HostedZoneId is not valid. Got",
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
            PUBLIC_DNS_ZONE_ID.title: zone_r["Id"].split(r"/")[-1],
            "ZoneName": LAST_DOT_RE.sub("", zone_r["Name"]),
        }
    except client.exceptions.InvalidDomainName:
        LOG.warning(f"Zone {zone.zone_name} is invalid or malformed.")


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


class HostedZone(AwsEnvironmentResource):
    """
    Class specifically for ACM Certificate

    :ivar list[Record] records: List of DNS Records to create with the DNS Zone
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        self.zone_name = None
        self.records = []
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.cloud_control_attributes_mapping = {PUBLIC_DNS_ZONE_ID.title: "Id"}
        self.zone_name = self.definition["ZoneName"]

    def init_outputs(self):
        """
        Returns the properties from the ACM Certificate
        """
        self.output_properties = {
            PUBLIC_DNS_ZONE_ID: (f"{self.logical_name}", self.cfn_resource, Ref, None)
        }

    def lookup_resource(
        self,
        arn_re,
        native_lookup_function,
        cfn_resource_type,
        tagging_api_id,
        subattribute_key=None,
    ):
        """
        Special lookup for Route53. Only needs

        :param re.Pattern arn_re:
        :param native_lookup_function:
        :param cfn_resource_type:
        :param tagging_api_id:
        :param subattribute_key:
        :return:
        """
        lookup_attributes = self.lookup
        if subattribute_key is not None:
            if not keyisset(subattribute_key, self.lookup):
                raise KeyError(
                    f"{self.module_name}.{self.name} - Lookup sub-key {subattribute_key} is not defined."
                )
            lookup_attributes = self.lookup[subattribute_key]
        if isinstance(lookup_attributes, bool):
            self.mappings = lookup_hosted_zone(self, self.lookup_session, False)
        elif isinstance(lookup_attributes, dict):
            if not keyisset("HostedZoneId", lookup_attributes):
                lookup_hosted_zone(self, self.lookup_session, False)
            else:
                lookup_hosted_zone(
                    self,
                    self.lookup_session,
                    False,
                    zone_id=lookup_attributes["HostedZoneId"],
                )

    def handle_x_dependencies(self, settings):
        """
        WIll go over all the new resources to create in the execution and search for properties that can be updated
        with itself

        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        for resource in settings.get_x_resources(include_mappings=False):
            if not resource.cfn_resource:
                continue
            resource_stack = resource.stack
            if not resource_stack:
                LOG.error(
                    f"resource {resource.name} has no `stack` attribute defined. Skipping"
                )
                continue
            mappings = [
                (Elbv2, handle_elbv2_records),
                (Certificate, handle_acm_records),
            ]
            for target in mappings:
                if isinstance(resource, target[0]) or issubclass(
                    type(resource), target[0]
                ):
                    target[1](
                        self,
                        self.stack,
                        resource,
                        resource_stack,
                        settings,
                    )


def resolve_lookup(lookup_resources, settings):
    """
    Lookup the ACM certificates in AWS and creates the CFN mappings for them

    :param list[HostedZone] lookup_resources: List of resources to lookup
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if not keyisset(MAPPINGS_KEY, settings.mappings):
        settings.mappings[MAPPINGS_KEY] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            ZONES_PATTERN, lookup_hosted_zone, CfnHostedZone.resource_type, ""
        )
        settings.mappings[MAPPINGS_KEY].update(
            {resource.logical_name: resource.mappings}
        )
        resource.init_outputs()
        resource.generate_outputs()
    LOG.debug(settings.mappings[MAPPINGS_KEY])


class XStack(ComposeXStack):
    """
    Root stack for x-route53 hosted zones

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    _title = "Route53 zones and records created from x-route53"

    def __init__(self, name: str, settings, **kwargs):
        """
        :param str name:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        self.x_to_x_mappings = []
        self.x_resource_class = HostedZone
        set_resources(settings, HostedZone, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        for resource in x_resources:
            resource.stack = self
        if new_resources:
            stack_template = build_template(self._title)
            super().__init__(name, stack_template, **kwargs)
            # define_acm_certs(new_resources, settings, self)
        else:
            self.is_void = True
        if lookup_resources:
            resolve_lookup(lookup_resources, settings)
        if use_resources:
            warnings.warn(f"{RES_KEY}. - Use is not yet supported.")
        self.module_name = MOD_KEY
