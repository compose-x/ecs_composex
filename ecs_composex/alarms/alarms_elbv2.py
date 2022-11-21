#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Functions to validate the inputs from Metrics for elbv2
https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-cloudwatch-metrics.html#load-balancer-metrics-alb
https://docs.aws.amazon.com/elasticloadbalancing/latest/network/load-balancer-cloudwatch-metrics.html
"""

import re

from troposphere import Ref

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters
from ecs_composex.elbv2.elbv2_params import LB_FULL_NAME, TGT_FULL_NAME


def handle_elbv2_dimension_mapping(alarms_stack, dimension, resource, settings):
    """
    Replaces x-elbv2::<name> with a pointer to the LB

    :param ecs_composex.alarms.alarms_stack.XStack alarms_stack: The alarms stack which has the alarm to modify
    :param troposphere.cloudwatch.MetricDimension dimension:
    :param ecs_composex.alarms.alarms_stack.Alarm resource:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return: The identified LB
    """
    if not isinstance(dimension.Value, str):
        LOG.debug(f"{dimension} - {type(dimension)}")
        return
    if not dimension.Value.startswith("x-elbv2"):
        LOG.debug(f"Dimension.Value is not elbv2: {dimension.Value}")
        return
    lb = settings.find_resource(dimension.Value)
    add_parameters(
        alarms_stack.stack_template,
        [lb.attributes_outputs[LB_FULL_NAME]["ImportParameter"]],
    )
    alarms_stack.Parameters.update(
        {
            lb.attributes_outputs[LB_FULL_NAME][
                "ImportParameter"
            ].title: lb.attributes_outputs[LB_FULL_NAME]["ImportValue"]
        }
    )
    dimension.Value = Ref(lb.attributes_outputs[LB_FULL_NAME]["ImportParameter"])
    LOG.info(
        f"x-alarms - Associated {lb.cfn_resource.title} to {alarms_stack.title} - {resource.name}"
    )


def get_target_lb(parts, dimension, resource, settings):
    """
    Identifies and returns the Elbv2 from the x-elbv2 defined

    :param re.Match parts: The re.Match from dimension.Value
    :param troposphere.cloudwatch.MetricDimension dimension:
    :param ecs_composex.alarms.alarms_stack.Alarm resource:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return: The ELBv2 object
    :rtype: ecs_composex.elbv2.elbv2_stack.Elbv2
    :raises: ValueError if the name provided does not match to an x-elbv2 resource
    """
    if not parts.group("lb"):
        raise ValueError(
            f"{resource.name} - {dimension.Value} - LB {parts.group('lb')} not defined in x-elbv2"
        )
    the_lb = settings.find_resource(f"x-elbv2::{parts.group('lb')}")
    return the_lb


def validate_tgt_input(dimension, settings):
    """
    Validates given input is conform to expect format

    :param troposphere.cloudwatch.MetricDimension dimension:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return: The parts matched from the input
    :rtype: re.Match
    :raises: ValueError
    """
    target_re = re.compile(
        r"x-elbv2::(?P<lb>[a-zA-Z0-9-_.]+)::(?P<svc>[a-zA-Z0-9-_.]+)::(?P<port>\d+)$"
    )
    parts = target_re.match(dimension.Value)
    if not parts and not dimension.Value.startswith("x-elbv2"):
        LOG.info(
            f"The Target Group value {dimension.Value} is not set for interpolation. Skipping"
        )
        return
    elif not (
        parts
        or (
            parts
            and not parts.group("lb")
            or not parts.group("svc")
            or not parts.group("port")
        )
    ):
        raise ValueError(
            "The mappings to the Target group is incorrect. Must match pattern",
            target_re.pattern,
            "Got",
            parts,
        )
    if parts.group("svc") not in [_.name for _ in settings.families.values()]:
        raise ValueError(
            f"alarms - Service {parts.group('svc')} not in the defined services",
            settings.families.keys(),
        )
    return parts


def handle_elbv2_target_group_dimensions(alarms_stack, dimension, resource, settings):
    """
    Matches up the x-elbv2::<lb>::<service>::port provided input to the new resource for alarms

    :param ecs_composex.alarms.alarms_stack.XStack alarms_stack: The alarms stack which has the alarm to modify
    :param troposphere.cloudwatch.MetricDimension dimension:
    :param ecs_composex.alarms.alarms_stack.Alarm resource:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if not isinstance(dimension.Value, str):
        LOG.warning(
            f"{alarms_stack.title}{resource.name} - Dimension {dimension.Name} value is {type(dimension.Value)}"
        )
        return
    parts = validate_tgt_input(dimension, settings)
    for family in settings.families.values():
        if family.name == parts.group("svc"):
            break
    else:
        raise KeyError(
            "alarms. unable to find services family",
            parts.group("svc"),
            "service families available",
            [_.name for _ in settings.families.values()],
        )
    port = int(parts.group("port"))
    the_tgt = None
    the_lb = get_target_lb(parts, dimension, resource, settings)
    for target_group in family.target_groups:
        if target_group.elbv2 == the_lb and target_group.Port == port:
            the_tgt = target_group
    if the_tgt is None:
        raise ValueError(
            f"Family {family.logical_name} has not target group associated with",
            the_lb.name,
            "Associated LBs",
            [tgt.elbv2.name for tgt in family.target_groups],
        )
    else:
        add_parameters(
            alarms_stack.stack_template,
            [the_tgt.attributes_outputs[TGT_FULL_NAME]["ImportParameter"]],
        )
        alarms_stack.Parameters.update(
            {
                the_tgt.attributes_outputs[TGT_FULL_NAME][
                    "ImportParameter"
                ].title: the_tgt.attributes_outputs[TGT_FULL_NAME]["ImportValue"]
            }
        )
        dimension.Value = Ref(
            the_tgt.attributes_outputs[TGT_FULL_NAME]["ImportParameter"]
        )
        LOG.info(
            f"x-alarms - Associated {the_tgt.title} to {alarms_stack.title} - {resource.name}"
        )
