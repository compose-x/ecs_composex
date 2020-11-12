#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from troposphere import Ref, AWS_NO_VALUE, Tags
from troposphere.certificatemanager import (
    Certificate as AcmCert,
    DomainValidationOption,
)

from ecs_composex.acm.acm_params import (
    RES_KEY,
)
from ecs_composex.common import (
    NONALPHANUM,
    keyisset,
)
from ecs_composex.common.compose_resources import set_resources
from ecs_composex.dns.dns_params import PUBLIC_DNS_ZONE_ID


class Certificate(object):
    """
    Class specifically for ACM Certificate
    """

    def __init__(self, name, definition, settings):
        self.name = name
        self.logical_name = NONALPHANUM.sub("", name)
        self.definition = deepcopy(definition)
        self.properties = (
            {}
            if not keyisset("Properties", self.definition)
            else self.definition["Properties"]
        )
        self.settings = (
            {}
            if not keyisset("Settings", self.definition)
            else self.definition["Settings"]
        )
        self.lookup = (
            None
            if not keyisset("Lookup", self.definition)
            else self.definition["Lookup"]
        )
        self.use = (
            None if not keyisset("Use", self.definition) else self.definition["Use"]
        )
        self.cfn_resource = None

    def validate_properties(self):
        """
        Method to validate certificate properties
        :return:
        """

    def create_acm_cert(self, dns_settings, root_stack):
        """
        Method to set the ACM Certificate definition
        :param dns_settings:
        :return:
        """
        validations = [
            DomainValidationOption(
                DomainName=self.properties["DomainName"],
                HostedZoneId=Ref(PUBLIC_DNS_ZONE_ID),
            )
        ]
        if keyisset("SubjectAlternativeNames", self.properties):
            for alt_domain in self.properties["SubjectAlternativeNames"]:
                validations.append(
                    DomainValidationOption(
                        DomainName=alt_domain, HostedZoneId=Ref(PUBLIC_DNS_ZONE_ID)
                    )
                )
        self.cfn_resource = AcmCert(
            self.logical_name,
            DomainName=self.properties["DomainName"],
            SubjectAlternativeNames=self.properties["SubjectAlternativeNames"]
            if keyisset("SubjectAlternativeNames", self.properties)
            else Ref(AWS_NO_VALUE),
            ValidationMethod="DNS",
            DomainValidationOptions=validations,
            Tags=Tags(
                Name=self.properties["DomainName"], ZoneId=Ref(PUBLIC_DNS_ZONE_ID)
            ),
        )
        root_stack.stack_template.add_resource(self.cfn_resource)


def define_acm_certs(new_resources, dns_settings, root_stack):
    """
    Function to create the certificates

    :param new_resources:
    :param dns_settings:
    :return:
    """
    for resource in new_resources:
        resource.create_acm_cert(dns_settings, root_stack)


def init_acm_certs(settings, dns_settings, root_stack):
    set_resources(settings, Certificate, RES_KEY)
    new_resources = [
        settings.compose_content[RES_KEY][cert_name]
        for cert_name in settings.compose_content[RES_KEY]
        if not settings.compose_content[RES_KEY][cert_name].lookup
    ]
    if new_resources and not dns_settings.create_public_zone:
        define_acm_certs(new_resources, dns_settings, root_stack)
    elif new_resources and dns_settings.create_public_zone:
        raise ValueError(
            "By design, you cannot create new ACM Certificates if you do not already have a public DNS Zone."
            "Validation via DNS can only work if the zone is functional and you cannot associate a pending cert."
        )
