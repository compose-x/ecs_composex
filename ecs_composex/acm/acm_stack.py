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
from troposphere import FindInMap, Ref, Tags
from troposphere.certificatemanager import Certificate as CfnAcmCertificate
from troposphere.certificatemanager import DomainValidationOption
from troposphere.elasticloadbalancingv2 import Certificate as ElbCertificate
from troposphere.elasticloadbalancingv2 import Listener, ListenerCertificate

from ecs_composex.acm.acm_params import CERT_ARN, MAPPINGS_KEY, MOD_KEY, RES_KEY
from ecs_composex.common import add_parameters, build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import (
    AwsEnvironmentResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.resources_import import (
    find_aws_properties_in_aws_resource,
    find_aws_resources_in_template_resources,
    import_record_properties,
)

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
        return cert_config
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
        self.init_outputs()
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
        if not resource.outputs:
            resource.generate_outputs()
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
        settings.mappings[RES_KEY].update({resource.logical_name: resource.mappings})


def get_supported_resources(root_stack, res_key, classes):
    """

    :param root_stack:
    :param res_key:
    :param classes:
    :return:
    """
    resources = []
    for nested_stack in root_stack.stack_template.resources.values():
        if not issubclass(type(nested_stack), ComposeXStack):
            continue
        if nested_stack.name == res_key or f"x-{nested_stack.name}" == res_key:

            for resource in nested_stack.stack_template.resources.values():

                if issubclass(type(resource), ComposeXStack):
                    resources += get_supported_resources(resource, res_key, classes)
                elif isinstance(resource, classes) or issubclass(
                    type(resource), classes
                ):
                    resources.append((nested_stack, resource))
    return resources


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
        self.x_to_x_mappings = x_to_x_settings = [
            (
                update_property_stack_with_resource,
                (Listener, ListenerCertificate),
                ElbCertificate,
                "CertificateArn",
            )
        ]
        self.x_resource_class = Certificate
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
        self.module_name = MOD_KEY
        for resource in x_resources:
            resource.stack = self


def update_property_stack_with_resource(
    x_resources, property_stack, properties_to_update, property_name, settings
):
    """
    Function to associate the resource

    :param list[Certificate] x_resources:
    :param ecs_composex.common.stacks.ComposeXStack property_stack:
    :param list properties_to_update:
    :param str property_name:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for prop_to_update in properties_to_update:
        if not hasattr(prop_to_update, property_name):
            raise AttributeError(
                f"{prop_to_update} does not have {property_name} set !?"
            )
        property_value = getattr(prop_to_update, property_name)
        if not isinstance(property_value, str):
            continue
        if not property_value.startswith(RES_KEY):
            continue
        if not property_value.find(RES_KEY) >= 0:
            LOG.info(
                f"{RES_KEY} - {property_value} is not a pointer to x-acm. {property_value}"
            )
            continue
        else:
            cert_name = property_value.split(r"::")[-1]
            the_cert = None
            for cert in x_resources:
                if cert.name == cert_name:
                    the_cert = cert
                    break
            if not the_cert:
                raise LookupError(
                    f"Cannot find {cert_name} in {RES_KEY} resources",
                    [res.name for res in x_resources],
                )
            update_stack_with_resource_settings(
                property_stack, the_cert, prop_to_update, property_name, settings
            )


def update_stack_with_resource_settings(
    property_stack, the_resource, the_property, property_name, settings
):
    """
    Assigns the CFN pointer to the value to replace.
    If it is a new certificate, it will add the parameter to get the cert ARN and set the parameter stack value
    If it is a Lookup certificate, it will add the mapping to the stack and set FindInMap to the certificate ARN

    :param ComposeXStack property_stack:
    :param Certificate the_resource:
    :param the_property:
    :param property_name:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if the_resource.cfn_resource:
        add_parameters(
            property_stack.stack_template,
            [the_resource.attributes_outputs[CERT_ARN]["ImportParameter"]],
        )
        property_stack.Parameters.update(
            {
                the_resource.attributes_outputs[CERT_ARN][
                    "ImportParameter"
                ].title: the_resource.attributes_outputs[CERT_ARN]["ImportValue"]
            }
        )
        setattr(
            the_property,
            property_name,
            Ref(the_resource.attributes_outputs[CERT_ARN]["ImportParameter"]),
        )
    elif the_resource.mappings:
        if keyisset(the_resource.mapping_key, property_stack.stack_template.mappings):
            property_stack.stack_template.mappings[the_resource.mapping_key].update(
                the_resource.mappings
            )
        else:
            property_stack.stack_template.add_mapping(
                MOD_KEY, settings.mappings[RES_KEY]
            )
        setattr(
            the_property,
            property_name,
            FindInMap(
                the_resource.mapping_key,
                the_resource.logical_name,
                the_resource.logical_name,
            ),
        )
