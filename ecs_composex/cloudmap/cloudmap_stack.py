# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module for ACM
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from troposphere.servicediscovery import PrivateDnsNamespace

if TYPE_CHECKING:
    from ecs_composex.mods_manager import XResourceModule, ModManager
    from ecs_composex.common.settings import ComposeXSettings

from copy import deepcopy

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import GetAtt

from ecs_composex.cloudmap.cloudmap_helpers import (
    detect_duplicas,
    lookup_service_discovery_namespace,
    resolve_lookup,
)
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_resource,
    add_update_mapping,
    build_template,
)
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.resources_import import import_record_properties
from ecs_composex.vpc.vpc_params import VPC_ID

from .cloudmap_params import (
    MOD_KEY,
    PRIVATE_DNS_ZONE_ID,
    PRIVATE_DNS_ZONE_NAME,
    PRIVATE_NAMESPACE_ID,
)
from .cloudmap_x_resources import handle_resource_cloudmap_settings


class PrivateNamespace(AwsEnvironmentResource):
    """
    Class specifically for ACM Certificate

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
        self.family_sd_services: dict = {}
        super().__init__(name, definition, module, settings)
        self.support_defaults = True
        self.zone_name = set_else_none(
            "Name", self.definition, set_else_none("ZoneName", self.definition, None)
        )
        if self.zone_name is None:
            raise ValueError(
                f"{self.module.res_key}.{self.name} - No ZoneName/Name specified"
            )
        self.requires_vpc = True

    def init_outputs(self):
        """
        Returns the properties outputs mappings.
        """
        self.output_properties = {
            PRIVATE_NAMESPACE_ID: (
                f"{self.logical_name}{PRIVATE_NAMESPACE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                PRIVATE_NAMESPACE_ID.return_value,
            ),
            PRIVATE_DNS_ZONE_ID: (
                f"{self.logical_name}{PRIVATE_DNS_ZONE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                PRIVATE_DNS_ZONE_ID.return_value,
            ),
            PRIVATE_DNS_ZONE_NAME: (
                f"{self.logical_name}{PRIVATE_DNS_ZONE_NAME.return_value}",
                self.cfn_resource,
                self.zone_name,
                False,
            ),
        }

    @property
    def namespace_id(self):
        if not self.attributes_outputs:
            return None
        return self.attributes_outputs[PRIVATE_NAMESPACE_ID]

    @property
    def hosted_zone_id(self):
        if not self.attributes_outputs:
            return None
        return self.attributes_outputs[PRIVATE_DNS_ZONE_ID]

    @property
    def zone_dns_name(self):
        if not self.attributes_outputs:
            return None
        return self.attributes_outputs[PRIVATE_DNS_ZONE_NAME]

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
        When creating new CloudMap records, if the x-cloudmap where looked up, we need to initialize the CloudMap stack
        """
        if self.stack.is_void:
            stack_template = build_template("Root stack for x-cloudmap resources")
            super(XStack, self.stack).__init__(MOD_KEY, stack_template)
            self.stack.is_void = False
            add_update_mapping(
                self.stack.stack_template,
                self.module.mapping_key,
                settings.mappings[self.module.mapping_key],
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
            add_resource(settings.root_stack.stack_template, self.stack)

    def add_initialized_stack_to_root(
        self, stack_initialized: bool, root_stack: ComposeXStack
    ) -> None:
        if (
            stack_initialized
            and self.stack.stack_template
            and self.stack.stack_template.resources
            and self.stack.title not in root_stack.stack_template.resources
        ):
            add_resource(root_stack.stack_template, self.stack)

    def to_ecs(
        self,
        settings: ComposeXSettings,
        modules: ModManager,
        root_stack: ComposeXStack = None,
    ) -> None:
        """
        Checks whether the namespace should be mapped to a given ECS Service
        :param ComposeXSettings settings: Execution settings
        :param ModManager modules: Unused atm
        :param ComposeXStack root_stack: Unused atm
        """
        from .cloudmap_ecs import create_registry

        for family in settings.families.values():
            if not family.service_networking.cloudmap_config:
                continue
            for (
                namespace,
                port_config,
            ) in family.service_networking.cloudmap_config.items():
                if namespace == self.name:
                    stack_initialized = False if self.stack.is_void else True
                    if not stack_initialized:
                        self.init_stack_for_resources(settings)
                    self.add_initialized_stack_to_root(stack_initialized, root_stack)
                    create_registry(family, self, port_config, settings)


class XStack(ComposeXStack):
    """
    Root stack for x-cloudmap

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    _title = "AWS CloudMap Namespaces"

    def __init__(
        self, name: str, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        """
        :param str name:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """

        detect_duplicas(module.resources_list)
        if module.new_resources:
            stack_template = build_template(self._title)
            super().__init__(module.mapping_key, stack_template, **kwargs)
            define_new_namespace(module.new_resources, stack_template)
        else:
            self.is_void = True
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)
        self.module_name = module.mod_key
        for resource in module.resources_list:
            resource.stack = self


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
                    f"{namespace.module.res_key}.{namespace.name} - "
                    "ZoneName and Properties.Name must be the same value when set."
                )
            elif not keyisset("Name", namespace.properties):
                namespace.properties["Name"] = namespace.zone_name

            namespace_props = import_record_properties(
                namespace.properties, PrivateNamespace
            )
            if keyisset("Vpc", namespace_props):
                LOG.warn(
                    f"{namespace.module.res_key}.{namespace.name} - "
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
                f"{namespace.module.res_key}.{namespace.name} - "
                "Failed to create PrivateNamespace from Properties/MacroParameters"
            )
        add_resource(stack_template, namespace.cfn_resource)
        namespace.init_outputs()
        namespace.generate_outputs()
        add_outputs(stack_template, namespace.outputs)
