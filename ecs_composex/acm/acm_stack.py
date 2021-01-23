#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Main module for ACM
"""

from copy import deepcopy
from warnings import warn

from troposphere import Ref, Tags
from troposphere.certificatemanager import (
    Certificate as AcmCert,
    DomainValidationOption,
)

from ecs_composex.acm.acm_aws import lookup_cert_config
from ecs_composex.acm.acm_params import RES_KEY, MOD_KEY
from ecs_composex.common import (
    NONALPHANUM,
    keyisset,
)
from ecs_composex.common.compose_resources import set_resources
from ecs_composex.dns.dns_params import PUBLIC_DNS_ZONE_ID
from ecs_composex.resources_import import import_record_properties


class Certificate(object):
    """
    Class specifically for ACM Certificate
    """

    def __init__(self, name, definition, settings):
        self.name = name
        self.logical_name = NONALPHANUM.sub("", name)
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

    def define_parameters_props(self, dns_settings):
        if not keyisset("DomainNames", self.parameters):
            raise KeyError(
                "For MacroParameters, you need to define at least DomainNames"
            )
        validations = [
            DomainValidationOption(
                DomainName=domain_name, HostedZoneId=dns_settings.public_zone.id_value
            )
            for domain_name in self.parameters["DomainNames"]
        ]
        props = {
            "DomainValidationOptions": validations,
            "DomainName": self.parameters["DomainNames"][0],
            "ValidationMethod": "DNS",
            "Tags": Tags(
                Name=self.parameters["DomainNames"][0],
                ZoneId=dns_settings.public_zone.id_value,
            ),
            "SubjectAlternativeNames": self.parameters["DomainNames"][1:],
        }
        return props

    def create_acm_cert(self, dns_settings):
        """
        Method to set the ACM Certificate definition
        """
        print(self.name, self.properties, self.parameters)
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
    set_resources(settings, Certificate, RES_KEY)
    new_resources = [
        settings.compose_content[RES_KEY][cert_name]
        for cert_name in settings.compose_content[RES_KEY]
        if not settings.compose_content[RES_KEY][cert_name].lookup
    ]
    lookup_resources = [
        settings.compose_content[RES_KEY][cert_name]
        for cert_name in settings.compose_content[RES_KEY]
        if settings.compose_content[RES_KEY][cert_name].lookup
    ]
    if new_resources:
        define_acm_certs(new_resources, dns_settings, root_stack)
    if new_resources and dns_settings.public_zone.create_zone:
        warn(
            "Validation via DNS can only work if the zone is functional and you cannot associate a pending cert."
            "CFN Will fail if the ACM cert validation is not complete."
        )
    if lookup_resources:
        mappings = create_acm_mappings(lookup_resources, settings)
        if mappings:
            root_stack.stack_template.add_mapping(MOD_KEY, mappings)
