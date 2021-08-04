#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to import existing ACM Certificates just as for other resources.
"""

from botocore.exceptions import ClientError
from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)


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


def get_cert_config(logical_name, cert_arn, session):
    """

    :param str cert_arn:
    :param boto3.session.Session session:
    :return:
    """
    cert_config = {logical_name: cert_arn}
    client = session.client("acm")
    try:
        cert_r = client.describe_certificate(CertificateArn=cert_arn)
        cert_config.update(
            {logical_name: {logical_name: cert_r["Certificate"]["CertificateArn"]}}
        )
        validate_certificate_status(cert_r["Certificate"])
        return cert_config
    except client.exceptions.ResourceNotFoundException:
        return None
    except client.exceptions.InvalidArnException:
        LOG.error(f"CertARN {cert_arn} is invalid?!?")
        raise
    except ClientError as error:
        LOG.error(error)
        raise


def lookup_cert_config(logical_name, lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    acm_types = {
        "acm:certificate": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:acm:[\S]+:[0-9]+:)certificate/([\S]+)$"
        },
    }
    lookup_session = define_lookup_role_from_info(lookup, session)
    cert_arn = find_aws_resource_arn_from_tags_api(
        lookup,
        lookup_session,
        "acm:certificate",
        types=acm_types,
    )
    if not cert_arn:
        return None
    config = get_cert_config(logical_name, cert_arn, lookup_session)
    LOG.debug(config)
    return config
