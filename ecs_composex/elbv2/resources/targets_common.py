#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .compose_target_group import ComposeTargetGroup
    from .merged_target_group import MergedTargetGroup

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Output, Ref, Sub

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.elbv2.elbv2_params import TGT_FULL_NAME, TGT_GROUP_ARN, TGT_GROUP_NAME


def set_tg_outputs(target_group: Union[MergedTargetGroup, ComposeTargetGroup]):

    target_group.output_properties.update(
        {
            TGT_GROUP_ARN: (target_group.title, target_group, Ref, None),
            TGT_GROUP_NAME: (
                f"{target_group.title}{TGT_GROUP_NAME.return_value}",
                target_group,
                GetAtt,
                TGT_GROUP_NAME.return_value,
                None,
            ),
            TGT_FULL_NAME: (
                f"{target_group.title}{TGT_FULL_NAME.return_value}",
                target_group,
                GetAtt,
                TGT_FULL_NAME.return_value,
                None,
            ),
        }
    )


def generate_tg_outputs(target_group: Union[ComposeTargetGroup, MergedTargetGroup]):
    for (
        attribute_parameter,
        output_definition,
    ) in target_group.output_properties.items():
        output_name = f"{target_group.title}{attribute_parameter.title}"
        value = target_group.set_new_resource_outputs(output_definition)
        target_group.attributes_outputs[attribute_parameter] = {
            "Name": output_name,
            "Output": Output(output_name, Value=value),
            "ImportParameter": Parameter(
                output_name,
                return_value=attribute_parameter.return_value,
                Type=attribute_parameter.Type,
            ),
            "ImportValue": GetAtt(
                target_group.stack,
                f"Outputs.{output_name}",
            ),
            "Original": attribute_parameter,
        }
    for attr in target_group.attributes_outputs.values():
        if keyisset("Output", attr):
            target_group.outputs.append(attr["Output"])


def set_new_tg_output(output_definition: tuple):
    if output_definition[2] is Ref:
        value = Ref(output_definition[1])
    elif output_definition[2] is GetAtt:
        value = GetAtt(output_definition[1], output_definition[3])
    elif output_definition[2] is Sub:
        value = Sub(output_definition[3])
    else:
        raise TypeError(
            f"3rd argument for {output_definition[0]} must be one of",
            (Ref, GetAtt, Sub),
            "Got",
            output_definition[2],
        )
    return value
