#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Manages x-route53 to x-acm
"""

from troposphere import Ref

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters, add_update_mapping
from ecs_composex.route53.route53_params import PUBLIC_DNS_ZONE_ID, validate_domain_name


def new_dns_zone(route53_zone, acm_stack, validation_option):
    """
    Update the HostedZoneId property when using a new Route53 zone

    :param route53_zone:
    :param acm_stack:
    :param troposphere.certificatemanager.DomainValidationOption validation_option:
    """
    zone_id_attribute = route53_zone.attributes_outputs[PUBLIC_DNS_ZONE_ID]
    add_parameters(acm_stack.stack_template, [zone_id_attribute["ImportParameter"]])
    acm_stack.Parameters.update(
        {zone_id_attribute["ImportParameter"].title: zone_id_attribute["ImportValue"]}
    )
    setattr(
        validation_option, "HostedZoneId", Ref(zone_id_attribute["ImportParameter"])
    )


def lookup_dns_zone(route53_zone, validation_option, acm_stack, settings):
    """
    Update the HostedZoneId property when using a lookup DNS zone

    :param route53_zone:
    :param troposphere.certificatemanager.DomainValidationOption validation_option:
    :param XStack acm_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    add_update_mapping(
        acm_stack.stack_template,
        route53_zone.module.mapping_key,
        settings.mappings[route53_zone.module.mapping_key],
    )
    zone_id_attribute = route53_zone.attributes_outputs[PUBLIC_DNS_ZONE_ID]
    setattr(validation_option, "HostedZoneId", zone_id_attribute["ImportValue"])


def update_route53_pointer(
    x_hosted_zone,
    validation_setting,
    route53_stack,
    target_cert,
    acm_stack,
    settings,
):
    """
    Iterates over each HostedZone and upon finding the right one
    :param ecs_composex.route53.route53_zone.HostedZone x_hosted_zone: List of HostedZones defined
    :param troposphere.certificatemanager.DomainValidationOption validation_setting:
    :param XStack route53_stack:
    :param ComposeXStack acm_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    if x_hosted_zone.cfn_resource and route53_stack.title not in acm_stack.DependsOn:
        acm_stack.DependsOn.append(route53_stack.title)
    validate_domain_name(validation_setting.DomainName, x_hosted_zone.zone_name)
    if x_hosted_zone.cfn_resource:
        new_dns_zone(x_hosted_zone, acm_stack, target_cert)
    elif x_hosted_zone.mappings:
        lookup_dns_zone(x_hosted_zone, validation_setting, acm_stack, settings)
    else:
        raise RuntimeError("Failed to associate route53 zone to acm validation option")


def handle_acm_records(
    x_hosted_zone, route53_stack, target_cert, acm_stack, settings, root_stack=None
):
    """
    Function to go over the ACM Certificate Domain validation options, and identifies x-route53 to map it to.

    :param ecs_composex.route53.route53_zone.HostedZone x_hosted_zone: HostedZone to evaluate.
    :param ecs_composex.common.stacks.ComposeXStack route53_stack:
    :param ecs_composex.acm.acm_stack.Certificate target_cert:
    :param ecs_composex.common.stacks.ComposeXStack acm_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if not target_cert.cfn_resource:
        LOG.debug(
            f"{target_cert.module.res_key}.{target_cert.name} - Not a new certificate. Skipping"
        )
        return
    validation_options = [
        validation
        for validation in target_cert.cfn_resource.DomainValidationOptions
        if hasattr(validation, "HostedZoneId")
        and isinstance(validation.HostedZoneId, str)
        and validation.HostedZoneId.startswith(x_hosted_zone.module.res_key)
    ]

    for validation_opt in validation_options:
        dns_zone_pointer = validation_opt.HostedZoneId.split(
            rf"{x_hosted_zone.module.res_key}::"
        )[-1]
        if dns_zone_pointer != x_hosted_zone.name:
            continue
        x_hosted_zone.init_stack_for_records(root_stack, settings)
        update_route53_pointer(
            x_hosted_zone,
            validation_opt,
            route53_stack,
            target_cert,
            acm_stack,
            settings,
        )
