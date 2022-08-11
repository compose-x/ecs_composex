#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.common.stacks import ComposeXStack
    from .acm_stack import Certificate

from botocore.exceptions import ClientError
from compose_x_common.aws.acm import ACM_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import Ref
from troposphere.certificatemanager import Certificate as CfnAcmCertificate

from ecs_composex.acm.acm_params import CERT_ARN, RES_KEY
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_parameters,
    add_resource,
    add_update_mapping,
)


def define_acm_certs(new_resources: list[Certificate], acm_stack: ComposeXStack):
    """
    Function to create the certificates

    :param list[Certificate] new_resources:
    :param ecs_composex.common.stacks.ComposeXStack acm_stack:
    """
    for resource in new_resources:
        resource.create_acm_cert()
        add_resource(acm_stack.stack_template, resource.cfn_resource)
        if not resource.outputs:
            resource.generate_outputs()
        if resource.outputs:
            acm_stack.stack_template.add_output(resource.outputs)


def resolve_lookup(
    lookup_resources: list[Certificate],
    settings: ComposeXSettings,
    module: XResourceModule,
) -> None:
    """
    Lookup the ACM certificates in AWS and creates the CFN mappings for them

    :param list[Certificate] lookup_resources: List of resources to lookup
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.mod_manager.XResourceModule module:
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            ACM_ARN_RE,
            get_cert_config,
            CfnAcmCertificate.resource_type,
            "acm:certificate",
        )
        resource.init_outputs()
        resource.generate_cfn_mappings_from_lookup_properties()
        resource.generate_outputs()
        LOG.info(
            f"{resource.module.res_key}.{resource.name} - Matched certificate {resource.arn}"
        )
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )


def update_property_stack_with_resource(
    x_certificate: Certificate,
    property_stack: ComposeXStack,
    properties_to_update: list,
    property_name: str,
    settings: ComposeXSettings,
) -> None:
    """
    Function to associate the resource

    :param Certificate x_certificate:
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
        if property_value.find(RES_KEY) < 0:
            LOG.info(
                f"{RES_KEY} - {property_value} is not a pointer to x-acm. {property_value}"
            )
        else:
            cert_name = property_value.split(r"::")[-1]
            if x_certificate.name == cert_name:
                update_stack_with_resource_settings(
                    property_stack,
                    x_certificate,
                    prop_to_update,
                    property_name,
                    settings,
                )


def update_stack_with_resource_settings(
    property_stack: ComposeXStack,
    the_resource: Certificate,
    the_property,
    property_name: str,
    settings: ComposeXSettings,
) -> None:
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
        if keyisset(
            the_resource.module.mapping_key, property_stack.stack_template.mappings
        ):
            property_stack.stack_template.mappings[the_resource.module.mapping_key][
                the_resource.logical_name
            ].update(the_resource.mappings)
        else:
            add_update_mapping(
                property_stack.stack_template,
                the_resource.module.mapping_key,
                settings.mappings[the_resource.module.mapping_key],
            )
        setattr(
            the_property,
            property_name,
            the_resource.attributes_outputs[CERT_ARN]["ImportValue"],
        )


def validate_certificate_status(certificate_definition: dict) -> None:
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


def get_cert_config(
    certificate: Certificate, account_id: str, resource_id: str
) -> dict | None:
    """
    Retrieves the AWS ACM Certificate details using AWS API
    """
    client = certificate.lookup_session.client("acm")
    cert_config = {}
    try:
        cert_r = client.describe_certificate(CertificateArn=certificate.arn)
        client.get_certificate(CertificateArn=cert_r["Certificate"]["CertificateArn"])
        cert_config[CERT_ARN] = cert_r["Certificate"]["CertificateArn"]
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
