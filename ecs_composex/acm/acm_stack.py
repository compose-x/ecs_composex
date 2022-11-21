# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module for ACM
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ecs_composex.acm.acm_stack_helpers import (
    define_acm_certs,
    resolve_lookup,
    update_property_stack_with_resource,
)

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

import re

from troposphere import Ref, Tags
from troposphere.certificatemanager import Certificate as CfnAcmCertificate
from troposphere.certificatemanager import DomainValidationOption
from troposphere.elasticloadbalancingv2 import Certificate as ElbCertificate
from troposphere.elasticloadbalancingv2 import Listener, ListenerCertificate

from ecs_composex.acm.acm_params import CERT_ARN
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.resources_import import (
    find_aws_properties_in_aws_resource,
    find_aws_resources_in_template_resources,
    import_record_properties,
)


class Certificate(AwsEnvironmentResource):
    """
    Class specifically for ACM Certificate
    """

    def init_outputs(self):
        """
        Returns the properties from the ACM Certificate
        """
        self.output_properties = {
            CERT_ARN: (f"{self.logical_name}", self.cfn_resource, Ref, None)
        }

    def define_parameters_props(self) -> dict:
        """
        Determines the Properties to use for new ACM Certificate

        :return: properties dict
        :rtype: dict
        """
        tag_filter = re.compile(r"(^\*.)")
        validations = [
            DomainValidationOption(
                DomainName=domain_name,
                HostedZoneId=self.parameters["HostedZoneId"],
            )
            for domain_name in self.parameters["DomainNames"]
        ]
        props = {
            "DomainValidationOptions": validations,
            "DomainName": self.parameters["DomainNames"][0],
            "ValidationMethod": "DNS",
            "Tags": Tags(
                Name=tag_filter.sub("wildcard.", self.parameters["DomainNames"][0]),
                ZoneId=self.parameters["HostedZoneId"],
            ),
            "SubjectAlternativeNames": self.parameters["DomainNames"][1:],
        }
        return props

    def create_acm_cert(self):
        """
        Method to set the ACM Certificate definition
        """
        if self.properties:
            props = import_record_properties(self.properties, CfnAcmCertificate)
        elif self.parameters:
            props = self.define_parameters_props()
        else:
            raise ValueError(
                "Failed to determine how to create the ACM certificate",
                self.logical_name,
            )

        self.cfn_resource = CfnAcmCertificate(f"{self.logical_name}AcmCert", **props)
        self.init_outputs()
        self.generate_outputs()

    def handle_x_dependencies(self, settings, root_stack):
        """

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ComposeXStack root_stack:
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
            x_to_x_mappings = [
                (
                    update_property_stack_with_resource,
                    (Listener, ListenerCertificate),
                    ElbCertificate,
                    "CertificateArn",
                )
            ]
            for update_settings in x_to_x_mappings:
                aws_resources_to_update = find_aws_resources_in_template_resources(
                    resource_stack, update_settings[1]
                )
                for stack_resource in aws_resources_to_update:
                    properties_to_update = find_aws_properties_in_aws_resource(
                        update_settings[2], stack_resource
                    )
                    update_settings[0](
                        self,
                        resource_stack,
                        properties_to_update,
                        update_settings[3],
                        settings,
                    )


class XStack(ComposeXStack):
    """
    Root stack for x-acm new certificates

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
        if module.new_resources:
            stack_template = build_template("ACM Certificates created from x-acm")
            super().__init__(name, stack_template, module=module, **kwargs)
            define_acm_certs(module.new_resources, self)
        else:
            self.is_void = True
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)
        self.module_name = module.mod_key
        for resource in module.resources_list:
            resource.stack = self
