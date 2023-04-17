# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for the XStack SSM
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.aws import get_account_id
from compose_x_common.aws.wafv2 import WAF_V2_WEB_ACL_ARN_RE, WAF_V2_WEB_ACL_REF_RE
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import GetAtt, Ref

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    add_resource,
    add_update_mapping,
    build_template,
)
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.wafv2_webacl.wafv2_webacl_params import (
    CONTROL_CLOUD_ATTR_MAPPING,
    WEB_ACL_ARN,
    WEB_ACL_ID,
    WEB_ACL_NAMESPACE,
    WEB_ACL_REF,
    WEB_ACL_WCU,
)
from ecs_composex.wafv2_webacl.wafv2_webacl_template import render_new_web_acls


class WebACL(AwsEnvironmentResource):
    """
    Class to represent a WebACL
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.ref_parameter = WEB_ACL_REF
        self.arn_parameter = WEB_ACL_ARN
        self.cloud_control_attributes_mapping = CONTROL_CLOUD_ATTR_MAPPING

    def init_outputs(self):
        self.output_properties = {
            WEB_ACL_REF: (self.logical_name, self.cfn_resource, Ref, None),
            WEB_ACL_ARN: (
                f"{self.logical_name}{WEB_ACL_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                WEB_ACL_ARN.return_value,
            ),
            WEB_ACL_ID: (
                f"{self.logical_name}{WEB_ACL_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                WEB_ACL_ID.return_value,
            ),
            WEB_ACL_NAMESPACE: (
                f"{self.logical_name}{WEB_ACL_NAMESPACE.return_value}",
                self.cfn_resource,
                GetAtt,
                WEB_ACL_NAMESPACE.return_value,
            ),
            # WEB_ACL_WCU: (
            #     f"{self.logical_name}{WEB_ACL_WCU.return_value}",
            #     self.cfn_resource,
            #     GetAtt,
            #     WEB_ACL_WCU.return_value,
            # ),
        }

    def lookup_resource(
        self,
        arn_re,
        native_lookup_function,
        cfn_resource_type,
        tagging_api_id: str = None,
        subattribute_key=None,
        use_arn_for_id: bool = False,
    ):
        """
        Method to self-identify properties. It will try to use AWS Cloud Control API if possible, otherwise fallback
        to using boto3 descriptions functions to create a mapping of the attributes.

        For WAFv2 given these do not have Tags, using CloudControl only.
        """
        self.init_outputs()
        wafv2_webacl_id = None
        lookup_attributes = self.lookup
        if subattribute_key is not None:
            lookup_attributes = self.lookup[subattribute_key]
        if keyisset("Identifier", lookup_attributes):
            if not WAF_V2_WEB_ACL_REF_RE.match(lookup_attributes["Identifier"]):
                raise ValueError(
                    "Identifier {} is invalid. Must match {}".format(
                        lookup_attributes["Identifier"], WAF_V2_WEB_ACL_REF_RE.pattern
                    )
                )
            wafv2_webacl_id = lookup_attributes["Identifier"]
        elif keyisset("Arn", lookup_attributes):
            LOG.info(f"{self.module.res_key}.{self.name} - Lookup via ARN")
            LOG.debug(
                f"{self.module.res_key}.{self.name} - ARN is {lookup_attributes['Arn']}"
            )
            arn_parts = arn_re.match(lookup_attributes["Arn"])
            if not arn_parts:
                raise KeyError(
                    f"{self.module.res_key}.{self.name} - ARN {lookup_attributes['Arn']} is not valid. Must match",
                    arn_re.pattern,
                )
            self.arn = lookup_attributes["Arn"]
            wafv2_webacl_id: str = "|".join(
                [
                    arn_parts.group("name"),
                    arn_parts.group("id"),
                    arn_parts.group("scope").upper(),
                ]
            )
        elif keyisset("Tags", lookup_attributes):
            raise AttributeError("Tags do not apply to AWS::WAFv2::WebACL")
        else:
            raise KeyError(f"{self.module.res_key}.{self.name} - You must specify Arn")
        if wafv2_webacl_id is None:
            raise LookupError(
                f"{self.module.res_key}.{self.name} - Failed to find the WAFv2 WebACL from either Identifier or ARN"
            )
        LOG.debug(
            "arn: %s - waf_id: %s",
            self.arn,
            wafv2_webacl_id,
        )
        props = self.cloud_control_attributes_mapping_lookup(
            cfn_resource_type, wafv2_webacl_id
        )
        self.lookup_properties = props
        self.generate_cfn_mappings_from_lookup_properties()
        self.generate_outputs()

    def init_stack(self, root_stack, settings: ComposeXSettings) -> None:
        """
        Initialize a XStack for resource associated with Lookup resources
        :param ComposeXStack root_stack: The root stack
        """

        if self.stack.is_void:
            stack_template = build_template("WAFv2 WebACL stack - Compose-X")
            super(XStack, self.stack).__init__("wafv2_webacl", stack_template)
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
        from ecs_composex.elbv2 import Elbv2
        from ecs_composex.wafv2_webacl.wafv2_webacl_elbv2 import handle_elbv2

        load_balancers = set_else_none("LoadBalancers", self.definition)
        if not load_balancers:
            return
        for resource in settings.get_x_resources(include_mappings=False):
            if not resource.cfn_resource:
                continue
            resource_stack = resource.stack
            if not resource_stack:
                LOG.debug(
                    f"resource {resource.name} has no `stack` attribute defined. Skipping"
                )
                continue
            mappings = [
                (Elbv2, handle_elbv2),
            ]
            for target in mappings:
                if isinstance(resource, target[0]) or issubclass(
                    type(resource), target[0]
                ):
                    if resource.name not in load_balancers:
                        continue
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


def resolve_lookup(lookup_resources, settings, module: XResourceModule):
    """
    Lookup of the AWS resources and setting the mappings for the resource type
    """
    from troposphere.wafv2 import WebACL as CfnWebACL

    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            WAF_V2_WEB_ACL_ARN_RE,
            None,
            CfnWebACL.resource_type,
        )
        LOG.info(f"{module.res_key}.{resource.name} - Matched to {resource.arn}")
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )


class XStack(ComposeXStack):
    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)

        if module.new_resources:
            template = build_template(f"WAFv2 WebAcl for {settings.name}")
            super().__init__(module.mapping_key, stack_template=template, **kwargs)
            render_new_web_acls(module.new_resources, self)
        else:
            self.is_void = True
        for resource in module.resources_list:
            resource.stack = self
