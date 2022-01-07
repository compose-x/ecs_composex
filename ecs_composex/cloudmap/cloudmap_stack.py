#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Main module for ACM
"""

import re
import warnings

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref
from troposphere.servicediscovery import PrivateDnsNamespace, PublicDnsNamespace

from ecs_composex.acm.acm_params import MAPPINGS_KEY, MOD_KEY, RES_KEY
from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import (
    AwsEnvironmentResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.resources_import import import_record_properties

from .cloudmap_params import (
    LAST_DOT_RE,
    MAPPINGS_KEY,
    MOD_KEY,
    PRIVATE_DNS_ZONE_ID,
    PRIVATE_DNS_ZONE_NAME,
    PRIVATE_NAMESPACE_ID,
    RES_KEY,
    ZONES_PATTERN,
)

LOG = setup_logging()


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


def lookup_service_discovery_namespace(zone, session, ns_id=None):
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
        print("ALL NAMES", namespaces)
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
                f"{zone.module_name}.{zone.name} - Failed to lookup {zone.zone_name}"
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


class PrivateNamespace(AwsEnvironmentResource):
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
        self.zone_name = self.definition["ZoneName"]
        self.requires_vpc = True

    def init_outputs(self):
        """
        Returns the properties outputs mappings.
        """
        self.output_properties = {
            PRIVATE_NAMESPACE_ID: (
                f"{self.logical_name}",
                self.cfn_resource,
                Ref,
                None,
            ),
            PRIVATE_DNS_ZONE_NAME: (
                f"{self.logical_name}{PRIVATE_DNS_ZONE_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                PRIVATE_NAMESPACE_ID.return_value,
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
                    f"{self.module_name}.{self.name} - Lookup sub-key {subattribute_key} is not defined."
                )
            lookup_attributes = self.lookup[subattribute_key]
        if isinstance(lookup_attributes, bool):
            self.mappings = lookup_service_discovery_namespace(
                self, self.lookup_session
            )
        elif isinstance(lookup_attributes, dict):
            if not keyisset("NamespaceId", lookup_attributes):
                lookup_service_discovery_namespace(self, self.lookup_session)
            else:
                lookup_service_discovery_namespace(
                    self,
                    self.lookup_session,
                    ns_id=lookup_attributes["NamespaceId"],
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
            ZONES_PATTERN,
            lookup_service_discovery_namespace,
            PrivateDnsNamespace.resource_type,
            "",
        )
        settings.mappings[MAPPINGS_KEY].update(
            {resource.logical_name: resource.mappings}
        )
        resource.init_outputs()
        resource.generate_outputs()
    LOG.debug(settings.mappings[MAPPINGS_KEY])


def define_new_namespace(new_namespaces, stack_template):
    """
    Creates new AWS CloudMap namespaces and associates it with the stack template

    :param list[PrivateNamespace] new_namespaces: list of PrivateNamespace to process
    :param troposphere.Template stack_template: The template to add the new resources to
    """
    for namespace in new_namespaces:
        if namespace.parameters and keyisset("AsPublicNamespace", namespace.parameters):
            namespace_props = import_record_properties(
                namespace.properties, PublicDnsNamespace
            )
            namespace.cfn_resource = PublicDnsNamespace(
                namespace.logical_name, **namespace_props
            )
        else:
            namespace_props = import_record_properties(
                namespace.properties, PrivateNamespace
            )
            if not keyisset("Vpc", namespace_props):
                LOG.warning(
                    f"{namespace.module_name}.{namespace.name} "
                    "Properties do not have Vpc. Will use x-vpc if defined"
                )
                namespace_props["Vpc"] = "x-vpc"
            namespace.cfn_resource = PrivateNamespace(
                namespace.logical_name, **namespace_props
            )
        stack_template.add_resource(namespace.cfn_resource)
        namespace.init_outputs()
        namespace.generate_outputs()


class XStack(ComposeXStack):
    """
    Root stack for x-cloudmap

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    _title = "AWS CloudMap Namespaces"

    def __init__(self, name: str, settings, **kwargs):
        """
        :param str name:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        self.x_to_x_mappings = []
        self.x_resource_class = PrivateNamespace
        set_resources(
            settings, PrivateNamespace, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY
        )
        x_resources = settings.compose_content[RES_KEY].values()
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        for resource in x_resources:
            resource.stack = self
        if new_resources:
            stack_template = build_template(self._title)
            super().__init__(name, stack_template, **kwargs)
            define_new_namespace(new_resources, stack_template)
        else:
            self.is_void = True
        if lookup_resources:
            resolve_lookup(lookup_resources, settings)
        if use_resources:
            warnings.warn(f"{RES_KEY}. - Use is not yet supported.")
        self.module_name = MOD_KEY
