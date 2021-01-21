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
Module to import existing ACM Certificates just as for other resources.
"""

from botocore.exceptions import ClientError

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.aws import (
    find_aws_resource_arn_from_tags_api,
    define_lookup_role_from_info,
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
