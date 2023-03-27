#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .alarms_stack import Alarm
    from troposphere import Template
    from ecs_composex.common.settings import ComposeXSettings

import re

from compose_x_common.compose_x_common import keyisset
from troposphere import (
    AWS_REGION,
    AWS_STACK_ID,
    FindInMap,
    GetAtt,
    Join,
    Ref,
    Select,
    Split,
    Sub,
)
from troposphere.cloudwatch import Alarm as CWAlarm
from troposphere.cloudwatch import CompositeAlarm, MetricDimension

from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.resources_import import import_record_properties


def map_expression_to_alarms(expression: str, alarms: list[Alarm]):
    """
    Function to map the alarms in expression to  CFN alarms

    :param str expression:
    :param list alarms:
    :return: The composite alarm properties
    :rtype: dict
    """
    alarms_re = re.compile(r"ALARM([\S]+)|OK([\S]+)|INSUFFICIENT_DATA([\S]+)")
    alarms_declared = alarms_re.findall(expression)
    alarms_filtered = []
    for alarm in alarms_declared:
        for name in alarm:
            if name is not None and len(name):
                alarms_filtered.append(name.strip().replace("(", "").replace(")", ""))
    defined_alarms = [alarm for alarm in alarms if alarm.cfn_resource]
    alarms_mapping = {}
    for alarm_name in alarms_filtered:
        if keyisset(alarm_name, alarms_mapping):
            continue
        for alarm in defined_alarms:
            if alarm.name == alarm_name:
                alarms_mapping[alarm_name] = alarm.cfn_resource
                alarm.in_composite = True
    return alarms_mapping


def create_composite_alarm_expression(mapping: dict, expression: str) -> Join:
    """
    Function to create the composite alarms

    :param dict mapping:
    :param str expression:
    :param list alarms:
    :return:
    """
    rendered_bits = []
    func_re = re.compile(
        r"((?:\(+)?(?:ALARM|OK|INSUFFICIENT_DATA))\(?([\S][^()]+)(?:\))(\)+)?"
    )
    for split in expression.split(" "):
        if func_re.match(split):
            groups = func_re.match(split).groups()
            func = groups[0]
            name = groups[1]
            closing = "" if not groups[2] else groups[2]
            if not keyisset(name, mapping):
                raise KeyError("There was no alarm identified to match name", name)
            alarm = mapping[name]
            rendered_bits.append(Sub(f"{func}(${{{alarm.title}}}){closing}"))
        else:
            rendered_bits.append(split.upper())
    rendered_expression = Join(" ", rendered_bits)
    return rendered_expression


def create_composite_alarm(alarm: Alarm, alarms: list[Alarm]) -> None:
    """
    Function to create the composite alarms
    """
    if alarm.properties and keyisset("AlarmRule", alarm.properties):
        eval_expression = alarm.properties["AlarmRule"]
    elif alarm.parameters and keyisset("CompositeExpression", alarm.parameters):
        eval_expression = alarm.parameters["CompositeExpression"]
    else:
        raise KeyError(
            "Either Properties.AlarmRule or MacroParameters.CompositeExpression must be set",
            alarm.properties,
            alarm.parameters,
        )
    mapping = map_expression_to_alarms(eval_expression, alarms)
    composite_expression = create_composite_alarm_expression(mapping, eval_expression)
    stack_id = Select(4, Split("-", Select(2, Split("/", Ref(AWS_STACK_ID)))))
    alarm_name = f"${{{AWS_REGION}}}-${{StackId}}-CompositeAlarmFor" + "".join(
        [a.title for a in mapping.values()]
    )
    alarm_name = (
        alarm_name[: (254 - 12)] if len(alarm_name) > (254 - 12) else alarm_name
    )
    if alarm.properties:
        props = import_record_properties(alarm.properties, CompositeAlarm)
        props.update(
            {
                "AlarmRule": composite_expression,
                "AlarmName": Sub(alarm_name, StackId=stack_id),
            }
        )
    else:
        props = {
            "AlarmRule": composite_expression,
            "AlarmName": Sub(alarm_name, StackId=stack_id),
            "ActionsEnabled": True,
        }
    alarm.properties = props
    alarm.cfn_resource = CompositeAlarm(
        alarm.logical_name,
        DependsOn=[a.title for a in mapping.values()],
        **props,
    )


def add_composite_alarms(template: Template, new_alarms: list[Alarm]) -> None:
    for alarm in new_alarms:
        if not alarm.cfn_resource and (
            (alarm.parameters and keyisset("CompositeExpression", alarm.parameters))
            or alarm.properties
        ):
            alarm.is_composite = True
            create_composite_alarm(alarm, new_alarms)
            add_resource(template, alarm.cfn_resource)
            alarm.init_outputs()
            alarm.generate_outputs()
            add_outputs(template, alarm.outputs)


def handle_service_alarm(
    alarm: Alarm, settings: ComposeXSettings, template: Template, family_name: str
) -> None:
    for family in settings.families.values():
        if family.name == family_name:
            break
    else:
        raise ValueError(
            f"{alarm.module.res_key}.{alarm.name} - MacroParameters.ServiceName",
            family_name,
            "Is not defined.",
            [_family.name for _family in settings.families.values()],
        )
    add_parameters(template, [CLUSTER_NAME, family.service_name_param])
    props = import_record_properties(alarm.properties, CWAlarm)
    props.update(
        {
            "Dimensions": [
                MetricDimension(**{"Name": "ClusterName", "Value": Ref(CLUSTER_NAME)}),
                MetricDimension(
                    **{
                        "Name": "ServiceName",
                        "Value": Ref(family.service_name_param),
                    }
                ),
            ],
        }
    )
    if settings.ecs_cluster.cfn_resource:
        alarm.stack.Parameters.update(
            {CLUSTER_NAME.title: Ref(settings.ecs_cluster.cfn_resource)}
        )
    else:
        alarm.stack.Parameters.update(
            {
                CLUSTER_NAME.title: FindInMap(
                    settings.ecs_cluster.mappings,
                    settings.ecs_cluster.mappings_key,
                    "Name",
                )
            }
        )
    alarm.stack.Parameters.update(
        {
            family.service_name_param.title: GetAtt(
                family.logical_name, f"Outputs.{family.service_name_param.title}"
            )
        }
    )
    alarm.cfn_resource = CWAlarm(alarm.logical_name, **props)
    alarm.init_outputs()
    alarm.generate_outputs()
    add_resource(template, alarm.cfn_resource)
    add_outputs(template, alarm.outputs)


def create_alarms(
    template: Template, stack, new_alarms: list[Alarm], settings: ComposeXSettings
) -> None:
    """
    Main function to create new alarms
    Rules out CompositeAlarms first, creates "Simple" alarms, and then link these to ComopsiteAlarms if so declared.
    """
    for alarm in new_alarms:
        alarm.stack = stack
        if alarm.parameters and keyisset("ServiceName", alarm.parameters):
            handle_service_alarm(
                alarm, settings, template, alarm.parameters["ServiceName"]
            )
        elif (
            alarm.properties
            and not alarm.parameters
            or (
                alarm.parameters
                and not keyisset("CompositeExpression", alarm.parameters)
            )
        ):
            try:
                import_record_properties(
                    alarm.properties,
                    CompositeAlarm,
                    ignore_missing_required=False,
                )
            except KeyError:
                props = import_record_properties(alarm.properties, CWAlarm)
                alarm.cfn_resource = CWAlarm(alarm.logical_name, **props)
                if alarm.cfn_resource.title not in template.resources:
                    alarm.init_outputs()
                    alarm.generate_outputs()
                    add_resource(template, alarm.cfn_resource)
                    add_outputs(template, alarm.outputs)
        elif alarm.parameters and keyisset("CompositeExpression", alarm.parameters):
            continue

    add_composite_alarms(template, new_alarms)
