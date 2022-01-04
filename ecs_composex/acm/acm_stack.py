#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Main module for ACM
"""

import re
import warnings

from botocore.exceptions import ClientError

# from compose_x_common.aws.acm import ACM_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import Ref, Tags
from troposphere.certificatemanager import Certificate as CfnAcmCertificate
from troposphere.certificatemanager import DomainValidationOption

from ecs_composex.acm.acm_params import CERT_ARN, MAPPINGS_KEY, MOD_KEY, RES_KEY
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

ACM_ARN_RE = re.compile(
    r"^arn:aws(?:-[a-z]+)?:acm:(?P<region>[\S]+):(?P<accountid>[\d]{12}):certificate/(?P<id>[\S]+)$"
)


LOG = setup_logging()


def validate_certificate_status(certificate_definition):
    """
    Function to verify a few things for the ACM Certificate

    :param dict certificate_definition:
    :return:
    """
    validations = certificate_definition["DomainValidationOptions"]
    for validation in validations:
        if (
            keyisset("ValidationStatus", validation)
            and validation["ValidationStatus"] != "SUCCESS"
        ):
            raise ValueError(
                f"The certificate {certificate_definition['CertificateArn']} is not valid."
            )


def get_cert_config(certificate, account_id, resource_id):
    """
    Retrieves the AWS ACM Certificate details using AWS API
    """
    client = certificate.lookup_session.client("acm")
    cert_config = {}
    try:
        cert_r = client.describe_certificate(CertificateArn=certificate.arn)
        client.get_certificate(CertificateArn=cert_r["Certificate"]["CertificateArn"])
        cert_config[certificate.logical_name] = cert_r["Certificate"]["CertificateArn"]
        validate_certificate_status(cert_r["Certificate"])

    except client.exceptions.RequestInProgressException:
        LOG.error(f"Certificate {certificate.arn} has not yet been issued.")
        raise
    except client.exceptions.ResourceNotFoundException:
        return None
    except client.exceptions.InvalidArnException:
        LOG.error(f"CertARN {certificate.arn} is invalid?!?")
        raise
    except ClientError as error:
        LOG.error(error)
        raise


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

    def create_acm_cert(self):
        """
        Method to set the ACM Certificate definition
        """
        if self.properties:
            props = import_record_properties(self.properties, CfnAcmCertificate)
        elif self.parameters:
            return
            # props = self.define_parameters_props(dns_settings)
        else:
            raise ValueError(
                "Failed to determine how to create the ACM certificate",
                self.logical_name,
            )

        self.cfn_resource = CfnAcmCertificate(f"{self.logical_name}AcmCert", **props)
        self.generate_outputs()


def define_acm_certs(new_resources, settings, acm_stack):
    """
    Function to create the certificates

    :param list[Certificate] new_resources:
    :param settings:
    :param ecs_composex.common.stacks.ComposeXStack acm_stack:
    """
    for resource in new_resources:
        resource.create_acm_cert()
        acm_stack.stack_template.add_resource(resource.cfn_resource)
        if resource.outputs:
            acm_stack.stack_template.add_output(resource.outputs)


def resolve_lookup(lookup_resources, settings):
    """
    Lookup the ACM certificates in AWS and creates the CFN mappings for them

    :param list[Certificate] lookup_resources: List of resources to lookup
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if not keyisset(RES_KEY, settings.mappings):
        settings.mappings[RES_KEY] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            ACM_ARN_RE,
            get_cert_config,
            CfnAcmCertificate.resource_type,
            "acm:certificate",
        )


class XStack(ComposeXStack):
    """
    Root stack for x-acm new certificates

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    def __init__(self, name: str, settings, **kwargs):
        """
        :param str name:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        set_resources(settings, Certificate, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = build_template("ACM Certificates created from x-acm")
            super().__init__(name, stack_template, **kwargs)
            define_acm_certs(new_resources, settings, self)
        else:
            self.is_void = True
        if lookup_resources:
            resolve_lookup(lookup_resources, settings)
        if use_resources:
            warnings.warn("x-acm.Use is not yet supported.")
