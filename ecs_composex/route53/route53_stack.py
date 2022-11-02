# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module for x-route53
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.route53.route53_helpers import resolve_lookup

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import Ref

from ecs_composex.acm.acm_stack import Certificate
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_resource,
    add_update_mapping,
    build_template,
)
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.elbv2.elbv2_stack import Elbv2
from ecs_composex.route53.route53_acm import handle_acm_records
from ecs_composex.route53.route53_elbv2 import handle_elbv2_records
from ecs_composex.route53.route53_helpers import lookup_hosted_zone
from ecs_composex.route53.route53_params import PUBLIC_DNS_ZONE_ID, PUBLIC_DNS_ZONE_NAME


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

    def init_stack_for_records(self, root_stack, settings: ComposeXSettings) -> None:
        """
        When creating new Route53 records, if the x-route53 where looked up, we need to initialize the Route53 stack

        :param ComposeXStack root_stack: The root stack
        """

        if self.stack.is_void:
            stack_template = build_template("Root stack for x-route53 resources")
            super(XStack, self.stack).__init__("route53", stack_template)
            self.stack.is_void = False
            add_update_mapping(
                self.stack.stack_template,
                self.module.mapping_key,
                settings.mappings[self.module.mapping_key],
            )
            add_resource(root_stack.stack_template, self.stack)

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


class XStack(ComposeXStack):
    """
    Root stack for x-route53 hosted zones

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

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
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)
        if module.new_resources:
            self.is_void = False
        else:
            self.is_void = True
        stack_template = build_template(module.res_key)
        super().__init__(module.mapping_key, stack_template, **kwargs)
        for resource in module.resources_list:
            resource.stack = self
