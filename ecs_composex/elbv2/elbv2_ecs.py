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

import re
import json

from troposphere import Ref, GetAtt
from troposphere import Parameter
from troposphere import AWS_NO_VALUE
from troposphere.elasticloadbalancingv2 import (
    TargetGroup,
    Matcher,
    TargetGroupAttribute,
)

from ecs_composex.common import keyisset
from ecs_composex.common import LOG
from ecs_composex.common.compose_resources import set_resources
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.vpc.vpc_params import VPC_ID
from ecs_composex.elbv2.elbv2_params import RES_KEY, LB_ARN, TGT_GROUP_ARN
from ecs_composex.elbv2.elbv2_stack import elbv2
from ecs_composex.resource_settings import get_selected_services


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
            print(
                f"Value for {ping_mapping[count][0]} is not valid. Must be in range of {ping_mapping[count][1]}"
            )
        props[ping_mapping[count][0]] = int(value)


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


def define_service_target_group(resource, family, target_definition):
    """
    Function to create the elbv2 TargetGroup

    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param dict target_definition:
    :return: target_group
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
    target_group = TargetGroup(
        f"{family.logical_name}TargetGroup{props['Port']}{resource.logical_name}",
        template=family.template,
        VpcId=Ref(VPC_ID),
        **props,
    )
    family.template.add_output(
        ComposeXOutput(
            target_group,
            [("", TGT_GROUP_ARN.title, Ref(target_group))],
            export=False,
        ).outputs
    )
    return target_group


def define_service_target_group_definition(resource, family, target_def):
    """
    Function to create the new service TGT Group

    :param ecs_composex.elbv2.elbv2_stack.elbv2 resource:
    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param dict target_def:
    :param list services:
    :return:
    """
    if resource.logical_name not in family.stack.DependsOn:
        family.stack.DependsOn.append(resource.logical_name)
        LOG.info(
            f"Added dependency between service family {family.logical_name} and {resource.logical_name}"
        )
    service_tgt_group = define_service_target_group(resource, family, target_def)
    output_attr = f"Outputs.{service_tgt_group.title}{TGT_GROUP_ARN.title}"
    LOG.debug(f"TGT GetAtt value {output_attr}")
    target_group_arn = GetAtt(
        family.stack.title,
        output_attr,
    )
    return target_group_arn


def handle_services_association(resource, services_stack):
    """
    Function to handle association of listeners and targets to the LB

    :param ecs_composex.elbv2.elbv2_stack.elbv2 resource:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :return:
    """
    for target in resource.families_targets:
        tgt_arn = define_service_target_group_definition(resource, target[1], target[2])
        for listener in resource.listeners:
            print("Looped over to ", listener.title)
            listener.map_services(target[0], tgt_arn)
    for listener in resource.listeners:
        print(listener.__dict__)
        listener.define_default_actions()
        print(listener.__dict__)
        # print(listener.to_dict())


def map_elbv2_to_services(settings, services_stack):
    """
    Function to generate the root template for ELBv2

    :param ecs_composex.common.settings ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :return:
    """
    set_resources(settings, elbv2, RES_KEY)
    resources = settings.compose_content[RES_KEY]
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    for resource in new_resources:
        resource.set_lb_definition(settings)
        resource.set_listeners(services_stack.stack_template)
        resource.associate_to_template(services_stack.stack_template)


def elbv2_to_ecs(services_stack, settings):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    for service in settings.services:
        print(service.name, service.my_family.template)
    map_elbv2_to_services(settings, services_stack)
    resources = settings.compose_content[RES_KEY]
    resource_mappings = {}
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].lookup and not resources[res_name].properties
    ]
    for resource in new_resources:
        handle_services_association(resource, services_stack)
