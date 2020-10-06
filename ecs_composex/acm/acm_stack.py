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

from warnings import warn

from troposphere import Ref, If, AWS_NO_VALUE, Tags
from troposphere.certificatemanager import (
    Certificate as AcmCert,
    DomainValidationOption,
)

from ecs_composex.acm import acm_conditions
from ecs_composex.acm.acm_params import (
    RES_KEY,
    CERT_CN,
    CERT_CN_T,
    CERT_ALT_NAMES,
    CERT_ALT_NAMES_T,
    VALIDATION_DOMAIN_ZONE_ID,
    VALIDATION_DOMAIN_ZONE_ID_T,
    VALIDATION_DOMAIN_NAME_T,
    VALIDATION_DOMAIN_NAME,
    CERT_VALIDATION_METHOD,
)
from ecs_composex.common import (
    NONALPHANUM,
    keyisset,
    build_template,
)
from ecs_composex.common.cfn_conditions import pass_root_stack_name
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.stacks import ComposeXStack


def initialize_acm_stack_template(cert_name):
    """
    Function to initialize a new certificate template
    :return:
    """
    tpl = build_template(
        "ACM Certificate",
        [
            VALIDATION_DOMAIN_ZONE_ID,
            VALIDATION_DOMAIN_NAME,
            CERT_VALIDATION_METHOD,
            CERT_CN,
            CERT_ALT_NAMES,
        ],
    )
    acm_conditions.add_all_conditions(tpl)
    cert = AcmCert(
        f"{cert_name}",
        template=tpl,
        DomainName=Ref(CERT_CN),
        SubjectAlternativeNames=If(
            acm_conditions.NO_ALT_NAMES_T, Ref(AWS_NO_VALUE), Ref(CERT_ALT_NAMES_T)
        ),
        ValidationMethod=Ref(CERT_VALIDATION_METHOD),
        DomainValidationOptions=[
            If(
                acm_conditions.USE_ZONE_ID_T,
                DomainValidationOption(
                    DomainName=Ref(CERT_CN),
                    HostedZoneId=Ref(VALIDATION_DOMAIN_ZONE_ID),
                ),
                If(
                    acm_conditions.ACM_ZONE_NAME_IS_NONE_T,
                    DomainValidationOption(
                        DomainName=Ref(CERT_CN),
                        HostedZoneId=Ref(VALIDATION_DOMAIN_ZONE_ID),
                    ),
                    DomainValidationOption(
                        DomainName=Ref(CERT_CN),
                        ValidationDomain=Ref(VALIDATION_DOMAIN_NAME),
                    ),
                ),
            )
        ],
        Tags=Tags(Name=Ref(CERT_CN)),
    )
    tpl.add_output(ComposeXOutput(cert, [(CERT_CN, "", Ref(cert))]).outputs)
    return tpl


def build_cert_params(cert_def):
    """
    Function to build the certificate parameters

    :param dict cert_def:
    :return: cert_params
    :rtype: dict
    """
    cert_params = {
        CERT_ALT_NAMES_T: Ref(CERT_ALT_NAMES)
        if keyisset("SubjectAlternativeNames", cert_def)
        else Ref(AWS_NO_VALUE),
        CERT_CN_T: cert_def["DomainName"],
        CERT_VALIDATION_METHOD.title: cert_def["ValidationMethod"]
        if keyisset("ValidationMethod", cert_def)
        else CERT_VALIDATION_METHOD.Default,
    }
    if keyisset("DomainValidationOptions", cert_def):
        options = cert_def["DomainValidationOptions"]
        if len(options) > 1:
            warn(
                ValueError(
                    "For now we are going to support only just the one validation methond."
                )
            )
        option = options[0]
        cert_params[VALIDATION_DOMAIN_ZONE_ID_T] = (
            option["HostedZoneId"]
            if keyisset("HostedZoneId", option)
            else VALIDATION_DOMAIN_ZONE_ID.Default
        )
        cert_params[VALIDATION_DOMAIN_NAME_T] = (
            cert_def["ValidationDomain"]
            if keyisset("ValidationDomain", option)
            else VALIDATION_DOMAIN_NAME.Default
        )
    return cert_params


def add_certificates(acm_tpl, certs):
    """
    Function to add all the ACM certs together
    :param acm_tpl:
    :param certs:

    :return:
    """
    for cert_name in certs:
        resource_name = NONALPHANUM.sub("", cert_name)
        cert_def = certs[cert_name]
        cert_props = cert_def["Properties"]
        cert_params = build_cert_params(cert_props)
        cert_params.update(pass_root_stack_name())
        cert_template = initialize_acm_stack_template(resource_name)
        acm_tpl.add_resource(
            ComposeXStack(
                resource_name,
                stack_template=cert_template,
                Parameters=cert_params,
            )
        )


def create_acm_template(settings):
    """
    Main entrypoint for ACM root template creation

    :param ecs_composex.common.settings.ComposeXSettings settings: The execution settings
    :return: root stack template for ACM.
    :rtype: troposphere.Template
    """
    if not keyisset(RES_KEY, settings.compose_content):
        return
    certs = settings.compose_content[RES_KEY]
    root_acm_tpl = build_template("Root template for ACM")
    add_certificates(root_acm_tpl, certs)
    return root_acm_tpl


class XStack(ComposeXStack):
    """
    XStack for ComposeX
    """

    def __init__(self, title, settings, **kwargs):
        template = create_acm_template(settings)
        super().__init__(title, stack_template=template, **kwargs)
