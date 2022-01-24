#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_REGION, AWS_STACK_NAME, GetAtt, Ref
from troposphere.route53 import AliasTarget, RecordSetType

from ecs_composex.common import NONALPHANUM, add_parameters, setup_logging
from ecs_composex.elbv2.elbv2_params import LB_DNS_NAME, LB_DNS_ZONE_ID

from .route53_params import PUBLIC_DNS_ZONE_ID, validate_domain_name

LOG = setup_logging()


def create_record(name, route53_zone, target_elbv2, elbv2_stack, settings):
    """
    Create a new RecordResource with the given DNS Name pointing to the ELB

    :param HostedZone route53_zone:
    :param ecs_composex.elbv2.elbv2_stack.Elbv2 target_elbv2:
    :param ComposeXStack elbv2_stack:
    :return: The RecordSetType pointing to the ELB
    :rtype: RecordSetType
    """
    elbv2_alias = AliasTarget(
        HostedZoneId=GetAtt(target_elbv2.cfn_resource, LB_DNS_ZONE_ID.return_value),
        DNSName=GetAtt(target_elbv2.cfn_resource, LB_DNS_NAME.return_value),
    )
    record_props = {
        "AliasTarget": elbv2_alias,
        "Region": Ref(AWS_REGION),
        "Type": "A",
        "Name": name,
    }
    if not keyisset("SetIdentifier", record_props):
        record_props["SetIdentifier"] = Ref(AWS_STACK_NAME)
    if route53_zone.cfn_resource:
        zone_id_attribute = route53_zone.attributes_outputs[PUBLIC_DNS_ZONE_ID]
        add_parameters(
            elbv2_stack.stack_template, [zone_id_attribute["ImportParameter"]]
        )
        elbv2_stack.Parameters.update(
            {
                zone_id_attribute["ImportParameter"].title: zone_id_attribute[
                    "ImportValue"
                ]
            }
        )
        record_props["HostedZoneId"] = Ref(zone_id_attribute["ImportParameter"])
    elif route53_zone.mappings:
        if route53_zone.mapping_key not in elbv2_stack.stack_template.mappings:
            elbv2_stack.stack_template.add_mapping(
                route53_zone.mapping_key, settings.mappings[route53_zone.mapping_key]
            )
        zone_id_attribute = route53_zone.attributes_outputs[PUBLIC_DNS_ZONE_ID]
        record_props["HostedZoneId"] = zone_id_attribute["ImportValue"]
    cfn_resource = RecordSetType(
        f"elbv2{target_elbv2.logical_name}Route53{record_props['Type']}{NONALPHANUM.sub('', record_props['Name'])}"[
            :128
        ],
        **record_props,
    )
    if cfn_resource.title not in elbv2_stack.stack_template.resources:
        elbv2_stack.stack_template.add_resource(cfn_resource)


def add_dns_records_for_elbv2(
    x_hosted_zone,
    record,
    route53_stack,
    target_elbv2,
    elbv2_stack,
    settings,
):
    """
    Iterates over each HostedZone and upon finding the right one
    :param ecs_composex.route53.route53_stack.HostedZone x_hosted_zone: List of HostedZones defined
    :param dict record:
    :param XStack route53_stack:
    :param AliasTarget elbv2_alias:
    :param ComposeXStack elbv2_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    if x_hosted_zone.cfn_resource and route53_stack.title not in elbv2_stack.DependsOn:
        elbv2_stack.DependsOn.append(route53_stack.title)
    dns_names = record["Names"]
    for name in dns_names:
        validate_domain_name(name, x_hosted_zone.zone_name)
        create_record(name, x_hosted_zone, target_elbv2, elbv2_stack, settings)
        LOG.info(
            f"{x_hosted_zone.module_name}{x_hosted_zone.name} - Created {name} for elbv2"
        )


def handle_elbv2_records(
    x_hosted_zone, route53_stack, target_elbv2, elbv2_stack, settings
):
    """
    Function to add DNS Records for ELBv2

    :param HostedZone x_hosted_zone: List of HostedZones defined
    :param XStack route53_stack:
    :param Elbv2 target_elbv2:
    :param ComposeXStack elbv2_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if not keyisset("DnsAliases", target_elbv2.definition):
        return
    records = target_elbv2.definition["DnsAliases"]

    for record in records:
        dns_zone = record["Route53Zone"]
        dns_zone_pointer = dns_zone.split(r"x-route53::")[-1]
        if dns_zone_pointer != x_hosted_zone.name:
            continue
        add_dns_records_for_elbv2(
            x_hosted_zone,
            record,
            route53_stack,
            target_elbv2,
            elbv2_stack,
            settings,
        )
