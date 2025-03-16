#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Output, Ref, Sub
from troposphere.elasticloadbalancingv2 import TargetGroup

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.elbv2.elbv2_params import TGT_FULL_NAME, TGT_GROUP_ARN, TGT_GROUP_NAME


class ComposeTargetGroup(TargetGroup):
    """
    Class to manage Target Groups
    """

    def __init__(
        self,
        title: str,
        elbv2: Elbv2,
        family: ComposeFamily,
        service: ComposeService,
        stack: ComposeXStack,
        port: int,
        **kwargs,
    ):
        self.family: ComposeFamily = family
        self.service: ComposeService = service
        self.stack: ComposeXStack = stack
        self.port: int = port
        self.outputs = []
        self.elbv2: Elbv2 = elbv2
        self.output_properties = {}
        self.attributes_outputs = {}
        super().__init__(title, **kwargs)

    def init_outputs(self):
        self.output_properties = {
            TGT_GROUP_ARN: (self.title, self, Ref, None),
            TGT_GROUP_NAME: (
                f"{self.title}{TGT_GROUP_NAME.return_value}",
                self,
                GetAtt,
                TGT_GROUP_NAME.return_value,
                None,
            ),
            TGT_FULL_NAME: (
                f"{self.title}{TGT_FULL_NAME.return_value}",
                self,
                GetAtt,
                TGT_FULL_NAME.return_value,
                None,
            ),
        }

    def generate_outputs(self):
        for (
            attribute_parameter,
            output_definition,
        ) in self.output_properties.items():
            output_name = f"{self.title}{attribute_parameter.title}"
            value = self.set_new_resource_outputs(output_definition)
            self.attributes_outputs[attribute_parameter] = {
                "Name": output_name,
                "Output": Output(output_name, Value=value),
                "ImportParameter": Parameter(
                    output_name,
                    return_value=attribute_parameter.return_value,
                    Type=attribute_parameter.Type,
                ),
                "ImportValue": GetAtt(
                    self.stack,
                    f"Outputs.{output_name}",
                ),
                "Original": attribute_parameter,
            }
        for attr in self.attributes_outputs.values():
            if keyisset("Output", attr):
                self.outputs.append(attr["Output"])

    def set_new_resource_outputs(self, output_definition):
        """
        Method to define the outputs for the resource when new
        """
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
