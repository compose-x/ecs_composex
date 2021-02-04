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

import re

from troposphere import AWS_NO_VALUE
from troposphere import Parameter
from troposphere import Ref, GetAtt
from troposphere.ecs import LoadBalancer as EcsLb
from troposphere.elasticloadbalancingv2 import (
    TargetGroup,
    Matcher,
    TargetGroupAttribute,
)

from ecs_composex.common import LOG
from ecs_composex.common import keyisset, add_parameters
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.elbv2.elbv2_params import TGT_GROUP_ARN
from ecs_composex.vpc.vpc_params import VPC_ID, SG_ID_TYPE
from ecs_composex.ecs.ecs_params import ELB_GRACE_PERIOD


def validate_tcp_health_counts(props):
    healthy_prop = "HealthyThresholdCount"
    unhealthy_prop = "UnhealthyThresholdCount"
    if (
        keyisset(healthy_prop, props)
        and keyisset(unhealthy_prop, props)
        and not props[unhealthy_prop] == props[healthy_prop]
    ):
        valid_value = max(props[unhealthy_prop], props[healthy_prop])
        LOG.warning(
            "With NLB your healthy and unhealthy count must be the same. Using the max of the two for cautious: "
            f"{valid_value}"
        )
        props[healthy_prop] = valid_value
        props[unhealthy_prop] = valid_value


def fix_nlb_settings(props):
    network_modes = ["TCP", "UDP", "TCP_UDP"]
    if (
        keyisset("HealthCheckProtocol", props)
        and not props["HealthCheckProtocol"] in network_modes
    ):
        return
    if keyisset("HealthCheckTimeoutSeconds", props):
        LOG.warning("With NLB you cannot set intervals. Resetting")
        props["HealthCheckTimeoutSeconds"] = Ref(AWS_NO_VALUE)
    if (
        keyisset("HealthCheckIntervalSeconds", props)
        and not (
            props["HealthCheckIntervalSeconds"] == 10
            or props["HealthCheckIntervalSeconds"] == 30
        )
        and not isinstance(props["HealthCheckIntervalSeconds"], Ref)
    ):
        right_value = min(
            [10, 30], key=lambda x: abs(x - props["HealthCheckIntervalSeconds"])
        )
        LOG.warning(
            f"The only intervals value valid for NLB are 10 and 30. Closes value is {right_value}"
        )
        props["HealthCheckIntervalSeconds"] = right_value
    validate_tcp_health_counts(props)


def handle_ping_settings(props, groups):
    """
    Function to setup the "ping" settings

    :param dict props:
    :param list, tuple groups:
    :return:
    """
    ping_mapping = (
        ("HealthyThresholdCount", (2, 10)),
        ("UnhealthyThresholdCount", (2, 10)),
        ("HealthCheckIntervalSeconds", (2, 120)),
        ("HealthCheckTimeoutSeconds", (2, 10)),
    )
    for count, value in enumerate(groups):
        if not min(ping_mapping[count][1]) <= int(value) <= max(ping_mapping[count][1]):
            LOG.error(
                f"Value for {ping_mapping[count][0]} is not valid. Must be in range of {ping_mapping[count][1]}"
            )
        props[ping_mapping[count][0]] = int(value)
    fix_nlb_settings(props)


def handle_path_settings(props, groups):
    """
    Function to set the path and codes properties

    :param dict props:
    :param list,tuple groups:
    :return:
    """
    if props["HealthCheckProtocol"] not in ["HTTP", "HTTPS"]:
        raise ValueError(
            groups,
            "Protocol and return codes are only valid for HTTP and HTTPS healthcheck",
        )
    path_re = re.compile(r"^[/]{1}[\S]+$")
    codes_re = re.compile(r"^[\d,]+$")
    for value in groups:
        if path_re.match(value):
            props["HealthCheckPath"] = value
        elif codes_re.match(value):
            props["Matcher"] = Matcher(HttpCode=value)


def handle_optional_settings(props, groups):
    """
    Function to handle optional parts of the healtcheck

    :param dict props:
    :param tuple, groups:
    :return:
    """
    ping_rex = r"^([\d]{1}|10):([\d]{1}|10):([\d]{1,3}):([\d]{1,3})$"
    ping_re = re.compile(ping_rex)
    path_rex = r"(?:.*):?([\/]{1}[\S]+):([\d,]+$)"
    path_re = re.compile(path_rex)
    handlers = [(path_re, handle_path_settings), (ping_re, handle_ping_settings)]
    for value in groups:
        for handle in handlers:
            if value and handle[0].match(value):
                handle[1](props, handle[0].match(value).groups())


def set_healthcheck_definition(props, target_definition):
    """

    :param dict props:
    :param dict target_definition:
    :return:
    """
    healthcheck_props = {
        "HealthCheckEnabled": Ref(AWS_NO_VALUE),
        "HealthCheckIntervalSeconds": Ref(AWS_NO_VALUE),
        "HealthCheckPath": Ref(AWS_NO_VALUE),
        "HealthCheckPort": Ref(AWS_NO_VALUE),
        "HealthCheckProtocol": Ref(AWS_NO_VALUE),
        "HealthCheckTimeoutSeconds": Ref(AWS_NO_VALUE),
        "HealthyThresholdCount": Ref(AWS_NO_VALUE),
    }
    required_mapping = (
        "HealthCheckPort",
        "HealthCheckProtocol",
    )
    required_rex = r"^([\d]{2,5}):(HTTPS|HTTP|TCP_UDP|TCP|TLS|UDP)$"
    healthcheck_regexp = (
        r"(^(?:[\d]{2,5}):(?:HTTPS|HTTP|TCP_UDP|TCP|TLS|UDP)):?"
        r"((?:[\d]{1}|10):(?:[\d]{1}|10):[\d]{1,3}:[\d]{1,3})?:?"
        r"([\/a-z0-9.-_][^:]+:[\d,]+$)?"
    )
    LOG.debug(healthcheck_regexp)
    healthcheck_reg = re.compile(healthcheck_regexp)
    if (
        keyisset("healthcheck", target_definition)
        and isinstance(target_definition["healthcheck"], str)
        and healthcheck_reg.match(target_definition["healthcheck"])
    ):
        groups = healthcheck_reg.match(target_definition["healthcheck"]).groups()
        required_re = re.compile(required_rex)
        for count, value in enumerate(required_re.match(groups[0]).groups()):
            healthcheck_props[required_mapping[count]] = value
        if len(groups) >= 2:
            try:
                handle_optional_settings(healthcheck_props, groups[1:])
            except ValueError:
                LOG.error(target_definition["name"], target_definition["healthcheck"])
                raise
    if (
        keyisset("healthcheck", target_definition)
        and isinstance(target_definition["healthcheck"], str)
        and not healthcheck_reg.match(target_definition["healthcheck"])
    ):
        LOG.error(target_definition["healthcheck"])
        raise ValueError(
            "The healthcheck pattern is not respected. Expected",
            "(healthcheck_port:protocol)(:healthy_count:unhealthy_count:intervals:timeout)?(:path?:match_codes)?",
        )
    props.update(healthcheck_props)


def validate_attributes(target_definition):
    """
    Function to validate services attributes
    :param dict target_definition:
    :return:
    """
    required_props = [
        ("port", int),
        ("healthcheck", str),
    ]
    if not all(
        prop in target_definition.keys() for prop in [key[0] for key in required_props]
    ):
        raise KeyError(
            "services require at least",
            [key[0] for key in required_props],
            "got",
            target_definition.keys(),
        )


def validate_props_and_service_definition(props, service):
    """
    Function to validate that the defined settings are valid according to the service definition.
    :param props:
    :param ecs_composex.common.compose_services.ComposeService service:
    :return:
    """
    valid_tcp = ["HTTP", "HTTPS", "TLS", "TCP_UDP", "TCP"]
    valid_udp = ["UDP", "TCP_UDP"]
    if not props["Port"] in [p["target"] for p in service.ports]:
        raise ValueError(
            f"Defined TargetGroup port {props['Port']} is not defined for {service.name}."
            " Valid ports are",
            [p["published"] for p in service.ports],
        )
    chosen_port = [p for p in service.ports if p["target"] == props["Port"]]
    if (chosen_port[0]["protocol"] == "tcp" and props["Protocol"] not in valid_tcp) or (
        chosen_port[0]["protocol"] == "udp" and props["Protocol"] not in valid_udp
    ):
        raise ValueError(
            f"The protocol defined for TargetGroup {props['Protocol']} "
            f"does not match the service protocol {chosen_port[0]['protocol']}"
        )


def handle_sg_lb_ingress_to_service(resource, family, resources_stack):
    """
    Function to add ingress from the LB to Target if using ALB
    :param resource:
    :param family:
    :param resources_stack:
    :return:
    """
    if resource.is_nlb():
        return
    lb_sg_param = Parameter(f"{resource.lb_sg.title}", Type=SG_ID_TYPE)
    add_parameters(family.template, [lb_sg_param])
    family.service_config.network.add_lb_ingress(
        family, lb_name=resource.logical_name, lb_sg_ref=Ref(lb_sg_param)
    )
    family.stack_parameters.update(
        {
            f"{resource.lb_sg.title}": GetAtt(
                resources_stack.title,
                f"Outputs.{resource.lb_sg.title}",
            )
        }
    )


def define_service_target_group(
    resource,
    service,
    family,
    resources_root_stack,
    target_definition,
):
    """
    Function to create the elbv2 target group
    :param ecs_composex.elbv2.elbv2_stack.Elbv2 resource:
    :param ecs_composex.common.compose_services.ComposeService service:
    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param ecs_composex.common.stacks.ComposeXStack resources_root_stack:
    :param dict target_definition:
    :return: the target group
    :rtype: troposphere.elasticloadbalancingv2.TargetGroup
    """
    validate_attributes(target_definition)
    props = {}
    set_healthcheck_definition(props, target_definition)
    props["Port"] = target_definition["port"]
    props["Protocol"] = (
        props["HealthCheckProtocol"]
        if not keyisset("protocol", target_definition)
        else target_definition["protocol"]
    )
    props["TargetType"] = "ip"
    props["TargetGroupAttributes"] = [
        TargetGroupAttribute(Key="deregistration_delay.timeout_seconds", Value="60")
    ]
    validate_props_and_service_definition(props, service)
    target_group = TargetGroup(
        f"Tgt{resource.logical_name}{family.logical_name}{service.logical_name}{props['Port']}",
        VpcId=Ref(VPC_ID),
        **props,
    )
    resources_root_stack.stack_template.add_resource(target_group)
    resources_root_stack.stack_template.add_output(
        ComposeXOutput(
            target_group,
            [("", TGT_GROUP_ARN.title, Ref(target_group))],
            export=False,
        ).outputs
    )
    tgt_parameter = Parameter(
        f"{target_group.title}Arn", Type="String", template=family.template
    )
    family.stack_parameters.update(
        {
            tgt_parameter.title: GetAtt(
                resources_root_stack.title,
                f"Outputs.{target_group.title}{TGT_GROUP_ARN.title}",
            )
        }
    )
    service_lb = EcsLb(
        ContainerPort=props["Port"],
        ContainerName=service.name,
        TargetGroupArn=Ref(tgt_parameter),
    )
    family.ecs_service.ecs_service.LoadBalancers.append(service_lb)
    add_parameters(family.template, [ELB_GRACE_PERIOD])
    family.ecs_service.ecs_service.HealthCheckGracePeriodSeconds = Ref(ELB_GRACE_PERIOD)
    handle_sg_lb_ingress_to_service(resource, family, resources_root_stack)
    return target_group


def define_service_target_group_definition(
    resource,
    service,
    family,
    target_def,
    resources_root_stack,
):
    """
    Function to create the new service TGT Group

    :param ecs_composex.elbv2.elbv2_stack.Elbv2 resource:
    :param service:
    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param dict target_def:
    :param ecs_composex.common.stacks.ComposeXStack resources_root_stack:
    :return:
    """
    if resource.logical_name not in family.stack.DependsOn:
        family.stack.DependsOn.append(resources_root_stack.title)
        LOG.info(
            f"Added dependency between service family {family.logical_name} and {resources_root_stack.title}"
        )

    service_tgt_group = define_service_target_group(
        resource,
        service,
        family,
        resources_root_stack,
        target_def,
    )
    return Ref(service_tgt_group)


def handle_services_association(resource, res_root_stack, settings):
    """
    Function to handle association of listeners and targets to the LB

    :param ecs_composex.elbv2.elbv2_stack.Elbv2 resource:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :return:
    """
    template = res_root_stack.stack_template
    stack = res_root_stack
    resource.set_listeners(template)
    resource.associate_to_template(template)
    identified = []
    for target in resource.families_targets:
        tgt_arn = define_service_target_group_definition(
            resource, target[0], target[1], target[2], res_root_stack
        )
        for service in resource.services:
            target_name = f"{target[1].name}:{target[0].name}"
            if target_name == service["name"]:
                service["target_arn"] = tgt_arn
                identified.append(True)
    if not identified or not (identified and all(identified)):
        raise LookupError(
            "Failed to define a TGT Group for any of",
            [target[0].name for target in resource.families_targets],
            "and map it for LB",
            resource.name,
        )

    for listener in resource.listeners:
        listener.map_services(resource)
    for listener in resource.listeners:
        listener.handle_certificates(settings, stack)
        listener.define_default_actions(template)


def elbv2_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map services, targets, listeners and ACM together

    :param dict resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    for resource in new_resources:
        handle_services_association(resource, res_root_stack, settings)
