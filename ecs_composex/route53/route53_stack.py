#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module for x-route53
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import Ref
from troposphere.route53 import HostedZone as CfnHostedZone

from ecs_composex.acm.acm_stack import Certificate
from ecs_composex.common import LOG, add_update_mapping, build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.elbv2.elbv2_stack import Elbv2
from ecs_composex.route53.route53_acm import handle_acm_records
from ecs_composex.route53.route53_elbv2 import handle_elbv2_records
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
    Class specifically for Route53 Hosted Zone

    :ivar list[Record] records: List of DNS Records to create with the DNS Zone
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        self.zone_name = None
        self.records = []
        super().__init__(name, definition, module, settings)
        self.cloud_control_attributes_mapping = {PUBLIC_DNS_ZONE_ID.title: "Id"}
        self.zone_name = set_else_none(
            "ZoneName", self.definition, set_else_none("Name", self.definition, None)
        )
        if self.zone_name is None:
            raise ValueError(
                f"{self.module.res_key}.{self.name} - Could not define the Zone Name"
            )

    def init_outputs(self):
        """
        Returns the properties for the Route53 zone
        """
        self.output_properties = {
            PUBLIC_DNS_ZONE_ID: (f"{self.logical_name}", self.cfn_resource, Ref, None),
            PUBLIC_DNS_ZONE_NAME: (
                f"{self.logical_name}{PUBLIC_DNS_ZONE_NAME.title}",
                None,
                self.zone_name,
                False,
            ),
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
                    f"{self.module.res_key}.{self.name} - Lookup sub-key {subattribute_key} is not defined."
                )
            lookup_attributes = self.lookup[subattribute_key]
        if isinstance(lookup_attributes, bool):
            self.lookup_properties = lookup_hosted_zone(
                self, self.lookup_session, False
            )
        elif isinstance(lookup_attributes, dict):
            if not keyisset("HostedZoneId", lookup_attributes):
                self.lookup_properties = lookup_hosted_zone(
                    self, self.lookup_session, False
                )
            else:
                self.lookup_properties = lookup_hosted_zone(
                    self,
                    self.lookup_session,
                    False,
                    zone_id=lookup_attributes["HostedZoneId"],
                )
        self.generate_cfn_mappings_from_lookup_properties()

    def init_stack_for_records(self, root_stack) -> None:
        """
        When creating new Route53 records, if the x-route53 where looked up, we need to initialize the Route53 stack

        :param ComposeXStack root_stack: The root stack
        """
        if self.module.mapping_key not in root_stack.stack_template.resources:
            stack_template = build_template(self.stack.stack_title)
            super(XStack, self.stack).__init__(self.module.mapping_key, stack_template)
            self.stack.is_void = False
            root_stack.stack_template.add_resource(self.stack)

    def handle_x_dependencies(self, settings, root_stack) -> None:
        """
        WIll go over all the new resources to create in the execution and search for properties that can be updated
        with itself

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ComposeXStack root_stack: The root stack
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
                    if (
                        self.mappings
                        and self.stack
                        and not self.stack.is_void
                        and self.stack.stack_template
                    ):
                        add_update_mapping(
                            self.stack.stack_template,
                            self.module.mapping_key,
                            settings.mappings[self.module.mapping_key],
                        )
                    target[1](
                        self, self.stack, resource, resource_stack, settings, root_stack
                    )


def resolve_lookup(
    lookup_resources: List[HostedZone],
    settings: ComposeXSettings,
    module: XResourceModule,
) -> None:
    """
    Lookup the ACM certificates in AWS and creates the CFN mappings for them

    :param list[HostedZone] lookup_resources: List of resources to lookup
    :param ecs_composex.common.settings.ComposeXSettings settings:
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


class XStack(ComposeXStack):
    """
    Root stack for x-route53 hosted zones

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    stack_title = "Route53 zones and records created from x-route53"

    def __init__(
        self, name: str, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        """
        :param str name:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        self.x_to_x_mappings = []
        self.x_resource_class = HostedZone
        set_resources(settings, HostedZone, module)
        x_resources = settings.compose_content[module.res_key].values()
        lookup_resources = set_lookup_resources(x_resources)
        if lookup_resources:
            resolve_lookup(lookup_resources, settings, module)
        new_resources = set_new_resources(x_resources, False)
        if new_resources:
            stack_template = build_template(self.stack_title)
            super().__init__(module.mapping_key, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in x_resources:
            resource.stack = self
