#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Main module for ACM
"""

import re
import warnings
from copy import deepcopy
from warnings import warn

from compose_x_common.compose_x_common import keyisset
from troposphere import Tags
from troposphere.certificatemanager import Certificate as AcmCert
from troposphere.certificatemanager import DomainValidationOption

from ecs_composex.acm.acm_aws import lookup_cert_config
from ecs_composex.acm.acm_params import MAPPINGS_KEY, MOD_KEY, RES_KEY
from ecs_composex.common import NONALPHANUM
from ecs_composex.common.compose_resources import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.resources_import import import_record_properties


class Certificate(object):
    """
    Class specifically for ACM Certificate
    """

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        self.name = name
        self.logical_name = NONALPHANUM.sub("", name)
        self.module_name = module_name
        self.mapping_key = mapping_key
        if self.mapping_key is None:
            self.mapping_key = self.module_name
        self.definition = deepcopy(definition)
        self.cfn_resource = None
        self.settings = (
            {}
            if not keyisset("Settings", self.definition)
            else self.definition["Settings"]
        )
        self.properties = {}
        self.lookup = (
            None
            if not keyisset("Lookup", self.definition)
            else self.definition["Lookup"]
        )
        self.use = (
            None if not keyisset("Use", self.definition) else self.definition["Use"]
        )
        if not self.lookup and not self.use and keyisset("Properties", self.definition):
            self.properties = self.definition["Properties"]
        self.parameters = (
            {}
            if not keyisset("MacroParameters", self.definition)
            else self.definition["MacroParameters"]
        )
        self.uses_default = not any(
            [self.lookup, self.parameters, self.use, self.properties]
        )

    def define_parameters_props(self, dns_settings):
        tag_filter = re.compile(r"(^\*.)")
        if not keyisset("DomainNames", self.parameters):
            raise KeyError(
                "For MacroParameters, you need to define at least DomainNames"
            )
        validations = [
            DomainValidationOption(
                DomainName=domain_name,
                HostedZoneId=dns_settings.public_zone.id_value,
            )
            for domain_name in self.parameters["DomainNames"]
        ]
        props = {
            "DomainValidationOptions": validations,
            "DomainName": self.parameters["DomainNames"][0],
            "ValidationMethod": "DNS",
            "Tags": Tags(
                Name=tag_filter.sub("wildcard.", self.parameters["DomainNames"][0]),
                ZoneId=dns_settings.public_zone.id_value,
            ),
            "SubjectAlternativeNames": self.parameters["DomainNames"][1:],
        }
        return props

    def create_acm_cert(self, dns_settings):
        """
        Method to set the ACM Certificate definition
        """
        if self.properties:
            props = import_record_properties(self.properties, AcmCert)
        elif self.parameters:
            props = self.define_parameters_props(dns_settings)
        else:
            raise ValueError(
                "Failed to determine how to create the ACM certificate",
                self.logical_name,
            )

        self.cfn_resource = AcmCert(f"{self.logical_name}AcmCert", **props)


def define_acm_certs(new_resources, dns_settings, root_stack):
    """
    Function to create the certificates

    :param list<Certificate> new_resources:
    :param dns_settings:
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    """
    for resource in new_resources:
        resource.create_acm_cert(dns_settings)
        root_stack.stack_template.add_resource(resource.cfn_resource)


def create_acm_mappings(resources, settings):
    """
    Function

    :param list resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    mappings = {}
    for res in resources:
        cert_config = lookup_cert_config(res.logical_name, res.lookup, settings.session)
        if cert_config:
            mappings.update(cert_config)
    return mappings


def init_acm_certs(settings, dns_settings, root_stack):
    set_resources(settings, Certificate, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
    x_resources = settings.compose_content[RES_KEY].values()
    new_resources = set_new_resources(x_resources, RES_KEY, False)
    lookup_resources = set_lookup_resources(x_resources, RES_KEY)
    use_resources = set_use_resources(x_resources, RES_KEY, False)
    if new_resources:
        define_acm_certs(new_resources, dns_settings, root_stack)
    if new_resources and dns_settings.public_zone.create_zone:
        warn(
            "Validation via DNS can only work if the zone is functional and you cannot associate a pending cert."
            "CFN Will fail if the ACM cert validation is not complete."
        )
    if lookup_resources:
        if not keyisset(RES_KEY, settings.mappings):
            settings.mapping[RES_KEY] = {}
        mappings = create_acm_mappings(lookup_resources, settings)
        if mappings:
            root_stack.stack_template.add_mapping(MOD_KEY, mappings)
            settings.mappings = mappings
    if use_resources:
        warnings.warn("x-acm.Use is not yet supported.")
