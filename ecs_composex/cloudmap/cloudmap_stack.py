#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module for ACM
"""

import warnings
from copy import deepcopy

from compose_x_common.aws.cloudmap import get_all_dns_namespaces
from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref
from troposphere.servicediscovery import PrivateDnsNamespace

from ecs_composex.common import add_update_mapping, build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import (
    AwsEnvironmentResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.exceptions import ComposeBaseException, IncompatibleOptions
from ecs_composex.resources_import import import_record_properties
from ecs_composex.vpc.vpc_params import VPC_ID

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
from .cloudmap_x_resources import handle_resource_cloudmap_settings

LOG = setup_logging()


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
            self.lookup_properties = lookup_service_discovery_namespace(
                self, self.lookup_session
            )
        elif isinstance(lookup_attributes, dict):
            if not keyisset("NamespaceId", lookup_attributes):
                self.lookup_properties = lookup_service_discovery_namespace(
                    self, self.lookup_session
                )
            else:
                self.lookup_properties = lookup_service_discovery_namespace(
                    self,
                    self.lookup_session,
                    ns_id=lookup_attributes["NamespaceId"],
                )

    def init_stack_for_resources(self, settings) -> None:
        """
        When creating new Route53 records, if the x-route53 where looked up, we need to initialize the Route53 stack

        :param ComposeXStack root_stack: The root stack
        """
        if self.stack.is_void:
            stack_template = build_template("Root stack for x-cloudmap resources")
            super(XStack, self.stack).__init__(MOD_KEY, stack_template)
            self.stack.is_void = False
            add_update_mapping(
                self.stack.stack_template,
                self.mapping_key,
                settings.mappings[self.mapping_key],
            )

    def handle_x_dependencies(self, settings, root_stack=None) -> None:
        """
        Allows to find resources that one wants to register in AWS CloudMap

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        """
        stack_initialized = False if self.stack.is_void else True
        for resource in settings.get_x_resources(include_mappings=True):
            if not resource.stack:
                LOG.debug(
                    f"resource {resource.name} has no `stack` attribute defined. Skipping"
                )
                continue
            if resource.cloudmap_settings:
                self.init_stack_for_resources(settings)
                if (
                    isinstance(resource.cloudmap_settings, str)
                    and resource.default_cloudmap_settings
                ):
                    cloudmap_settings = deepcopy(resource.default_cloudmap_settings)
                    cloudmap_settings["Namespace"] = resource.cloudmap_settings
                    cloudmap_settings["ForceRegister"] = True
                    handle_resource_cloudmap_settings(
                        self, resource, cloudmap_settings, settings
                    )
                elif isinstance(resource.cloudmap_settings, dict):
                    handle_resource_cloudmap_settings(
                        self, resource, resource.cloudmap_settings, settings
                    )
        if (
            stack_initialized
            and self.stack.stack_template
            and self.stack.stack_template.resources
            and self.stack.title not in root_stack.stack_template.resources
        ):
            root_stack.stack_template.add_resource(self.stack)


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
        resource.init_outputs()
        resource.generate_cfn_mappings_from_lookup_properties()
        resource.generate_outputs()
        settings.mappings[MAPPINGS_KEY].update(
            {resource.logical_name: resource.mappings}
        )
    LOG.debug(settings.mappings[MAPPINGS_KEY])


def define_new_namespace(new_namespaces, stack_template):
    """
    Creates new AWS CloudMap namespaces and associates it with the stack template

    :param list[PrivateNamespace] new_namespaces: list of PrivateNamespace to process
    :param troposphere.Template stack_template: The template to add the new resources to
    """
    for namespace in new_namespaces:
        if namespace.properties:
            if (
                keyisset("Name", namespace.properties)
                and namespace.zone_name != namespace.properties["Name"]
            ):
                raise ValueError(
                    f"{namespace.module_name}.{namespace.name} - "
                    "ZoneName and Properties.Name must be the same value when set."
                )
            elif not keyisset("Name", namespace.properties):
                namespace.properties["Name"] = namespace.zone_name

            namespace_props = import_record_properties(
                namespace.properties, PrivateNamespace
            )
            if keyisset("Vpc", namespace_props):
                LOG.warn(
                    f"{namespace.module_name}.{namespace.name} - "
                    "Vpc property was set. Overriding to compose-x x-vpc defined for execution."
                )
            namespace_props["Vpc"] = f"x-vpc::{VPC_ID.title}"
            namespace.cfn_resource = PrivateNamespace(
                namespace.logical_name, **namespace_props
            )
        elif namespace.uses_default:
            namespace_props = import_record_properties(
                {"Name": namespace.zone_name, "Vpc": f"x-vpc::{VPC_ID.title}"},
                PrivateDnsNamespace,
            )
            namespace.cfn_resource = PrivateDnsNamespace(
                namespace.logical_name, **namespace_props
            )
        if not namespace.cfn_resource:
            raise AttributeError(
                f"{namespace.module_name}.{namespace.name} - "
                "Failed to create PrivateNamespace from Properties/MacroParameters"
            )
        stack_template.add_resource(namespace.cfn_resource)
        namespace.init_outputs()
        namespace.generate_outputs()


def x_cloud_lookup_and_new_vpc(settings, vpc_stack):
    """
    Function to ensure there is no x-cloudmap.Lookup resource and Compose-X is creating a new VPC.
    The Namespace (CloudMap PrivateNamespace) cannot span across multiple VPC

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param vpc_stack: The VPC Stack
    :raises: IncompatibleOptions
    """
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


def detect_duplicas(x_resources: list):
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
        set_resources(
            settings, PrivateNamespace, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY
        )
        x_resources = settings.compose_content[RES_KEY].values()
        detect_duplicas(x_resources)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        new_resources = set_new_resources(
            x_resources, RES_KEY, supports_uses_default=True
        )
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
