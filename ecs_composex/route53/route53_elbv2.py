#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_REGION, AWS_STACK_NAME, GetAtt, Ref
from troposphere.route53 import AliasTarget, RecordSetType

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
)
from ecs_composex.elbv2.elbv2_params import LB_DNS_NAME, LB_DNS_ZONE_ID
from ecs_composex.route53.route53_params import PUBLIC_DNS_ZONE_ID, validate_domain_name


def create_record(name, route53_zone, route53_stack, target_elbv2, elbv2_stack) -> None:
    """
    Create a new RecordResource with the given DNS Name pointing to the ELB

    :param str name:
    :param ecs_composex.route53.route53_zone.HostedZone route53_zone:
    :param ecs_composex.route53.route53_stack.XStack route53_stack:
    :param ecs_composex.elbv2.elbv2_stack.Elbv2 target_elbv2:
    :param ComposeXStack elbv2_stack:
    """
    if not target_elbv2.attributes_outputs:
        target_elbv2.init_outputs()
        target_elbv2.generate_outputs()
        add_outputs(elbv2_stack.stack_template, target_elbv2.outputs)
    lb_zone_id = target_elbv2.attributes_outputs[LB_DNS_ZONE_ID]
    lb_dns_name = target_elbv2.attributes_outputs[LB_DNS_NAME]
    add_parameters(
        route53_stack.stack_template,
        [lb_zone_id["ImportParameter"], lb_dns_name["ImportParameter"]],
    )
    route53_stack.Parameters.update(
        {
            lb_zone_id["ImportParameter"].title: lb_zone_id["ImportValue"],
            lb_dns_name["ImportParameter"].title: lb_dns_name["ImportValue"],
        }
    )
    elbv2_alias = AliasTarget(
        HostedZoneId=Ref(lb_zone_id["ImportParameter"]),
        DNSName=Ref(lb_dns_name["ImportParameter"]),
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
        zone_id_attribute = GetAtt(
            route53_zone.cfn_resource, PUBLIC_DNS_ZONE_ID.return_value
        )
        record_props["HostedZoneId"] = zone_id_attribute
    elif route53_zone.mappings:
        zone_id_attribute = route53_zone.attributes_outputs[PUBLIC_DNS_ZONE_ID]
        record_props["HostedZoneId"] = zone_id_attribute["ImportValue"]
    cfn_resource = RecordSetType(
        f"elbv2{target_elbv2.logical_name}Route53{record_props['Type']}{NONALPHANUM.sub('', record_props['Name'])}"[
            :128
        ],
        **record_props,
    )
    if cfn_resource.title not in route53_stack.stack_template.resources:
        add_resource(route53_stack.stack_template, cfn_resource)
        if route53_stack.is_void:
            route53_stack.is_void = False
    if elbv2_stack.title not in route53_stack.DependsOn:
        route53_stack.DependsOn.append(elbv2_stack.title)


def add_dns_records_for_elbv2(
    x_hosted_zone,
    record,
    route53_stack,
    target_elbv2,
    elbv2_stack,
) -> None:
    """
    Iterates over each HostedZone and upon finding the right one
    :param ecs_composex.route53.route53_zone.HostedZone x_hosted_zone: List of HostedZones defined
    :param dict record:
    :param XStack route53_stack:
    :param ecs_composex.elbv2.elbv2_stack.Elbv2 target_elbv2:
    :param ComposeXStack elbv2_stack:
    """
    if x_hosted_zone.cfn_resource and route53_stack.title not in elbv2_stack.DependsOn:
        elbv2_stack.DependsOn.append(route53_stack.title)
    dns_names = record["Names"]
    for name in dns_names:
        validate_domain_name(name, x_hosted_zone.zone_name)
        create_record(name, x_hosted_zone, route53_stack, target_elbv2, elbv2_stack)
        LOG.info(
            f"{x_hosted_zone.module.res_key}.{x_hosted_zone.name} - "
            f"Created {name} for {target_elbv2.module.res_key}.{target_elbv2.name}"
        )


def handle_elbv2_records(
    x_hosted_zone,
    route53_stack,
    target_elbv2,
    elbv2_stack,
    settings=None,
    root_stack=None,
) -> None:
    """
    Function to add DNS Records for ELBv2

    :param HostedZone x_hosted_zone: List of HostedZones defined
    :param XStack route53_stack:
    :param Elbv2 target_elbv2:
    :param ComposeXStack elbv2_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings: unused. Present for compatibility.
    """
    if not keyisset("DnsAliases", target_elbv2.definition):
        return
    records = target_elbv2.definition["DnsAliases"]
    for record in records:
        dns_zone = record["Route53Zone"]
        dns_zone_pointer = dns_zone.split(r"x-route53::")[-1]
        if dns_zone_pointer != x_hosted_zone.name:
            continue
        x_hosted_zone.init_stack_for_records(root_stack, settings)
        add_dns_records_for_elbv2(
            x_hosted_zone,
            record,
            route53_stack,
            target_elbv2,
            elbv2_stack,
        )
