#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to validate the inputs from Metrics for elbv2
https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-cloudwatch-metrics.html#load-balancer-metrics-alb
https://docs.aws.amazon.com/elasticloadbalancing/latest/network/load-balancer-cloudwatch-metrics.html
"""

import re

from troposphere import Ref

from ecs_composex.common import add_parameters, setup_logging
from ecs_composex.elbv2.elbv2_params import LB_NAME, TGT_FULL_NAME

LOG = setup_logging()


def handle_elbv2_dimension_mapping(alarms_stack, dimension, resource, settings):
    """
    Replaces x-elbv2::<name> with a pointer to the LB

    :param ecs_composex.alarms.alarms_stack.XStack alarms_stack: The alarms stack which has the alarm to modify
    :param troposphere.cloudwatch.MetricDimension dimension:
    :param ecs_composex.alarms.alarms_stack.Alarm resource:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return: The identified LB
    """
    x_elbv2 = settings.compose_content["x-elbv2"]
    if not isinstance(dimension.Value, str):
        LOG.warning(
            f"{alarms_stack.title}{resource.name} - Dimension {dimension.Name} value is {type(dimension.Value)}"
        )
        return
    lb_name = dimension.Value.split("x-elbv2::")[-1]
    if lb_name not in x_elbv2.keys():
        raise ValueError(f"x-elbv2.{lb_name} is not present in this execution")
    lb = x_elbv2[lb_name]
    add_parameters(
        alarms_stack.stack_template, [lb.attributes_outputs[LB_NAME]["ImportParameter"]]
    )
    alarms_stack.Parameters.update(
        {
            lb.attributes_outputs[LB_NAME][
                "ImportParameter"
            ].title: lb.attributes_outputs[LB_NAME]["ImportValue"]
        }
    )
    dimension.Value = Ref(lb.attributes_outputs[LB_NAME]["ImportParameter"])
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
    x_elbv2 = settings.compose_content["x-elbv2"]
    if parts.group("lb") and not parts.group("lb") in x_elbv2.keys():
        raise ValueError(
            f"{resource.name} - {dimension.Value} - LB {parts.group('lb')} does not exist in x-elbv2",
            x_elbv2.keys(),
        )
    else:
        return x_elbv2[parts.group("lb")]


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
    if parts.group("svc") not in settings.families.keys():
        raise ValueError(
            f"the service {parts.group('svc')} not in the defined services",
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
    family = settings.families[parts.group("svc")]
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
