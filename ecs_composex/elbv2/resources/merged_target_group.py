#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ecs.ecs_family import ComposeFamily

from troposphere import Ref
from troposphere.ecs import LoadBalancer as EcsLb
from troposphere.elasticloadbalancingv2 import TargetGroup

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.troposphere_tools import add_parameters
from ecs_composex.ecs.ecs_params import ELB_GRACE_PERIOD
from ecs_composex.elbv2.elbv2_ecs.common import handle_sg_lb_ingress_to_service
from ecs_composex.elbv2.elbv2_params import TGT_GROUP_ARN

from .targets_common import generate_tg_outputs, set_new_tg_output, set_tg_outputs


class MergedTargetGroup(TargetGroup):
    """Class for TargetGroup merged among more than one service"""

    def __init__(
        self,
        name: str,
        definition: dict,
        elbv2: Elbv2,
        stack: ComposeXStack,
        port: int,
        **kwargs,
    ):
        self.name = name
        self._definition = definition
        self.families: list[ComposeFamily] = []
        self.stack: ComposeXStack = stack
        self.outputs = []
        self.elbv2: Elbv2 = elbv2
        self.output_properties = {}
        self.attributes_outputs = {}
        super().__init__(NONALPHANUM.sub("", name), **kwargs)

    @property
    def definition(self) -> dict:
        return self._definition

    def init_outputs(self):
        set_tg_outputs(self)

    def generate_outputs(self):
        generate_tg_outputs(self)

    def set_new_resource_outputs(self, output_definition):
        return set_new_tg_output(output_definition)

    def associate_families(self, settings: ComposeXSettings):
        for _family in self.definition["Services"]:
            _family_name, _service_name = _family["Name"].split(r":")
            for family in settings.families.values():
                if family.name == _family_name:
                    break
            else:
                raise KeyError(
                    f"{self.elbv2.module.res_key}.{self.elbv2.name} - TargetGroup {self.name} - Service Family {_family_name} is not set in services"
                )
            for _f_service in family.services:
                if _f_service.name == _service_name:
                    break
            else:
                raise KeyError(
                    f"{self.elbv2.module.res_key}.{self.elbv2.name} - TargetGroup {self.name} - Family {_family_name} does not have a container named {_service_name}"
                )

            if self not in family.target_groups:
                family.target_groups.append(self)
            tgt_parameter = self.attributes_outputs[TGT_GROUP_ARN]["ImportParameter"]
            add_parameters(family.template, [tgt_parameter])
            family.stack.Parameters.update(
                {
                    tgt_parameter.title: self.attributes_outputs[TGT_GROUP_ARN][
                        "ImportValue"
                    ],
                }
            )
            service_lb = EcsLb(
                ContainerPort=self.Port,
                ContainerName=_f_service.name,
                TargetGroupArn=Ref(tgt_parameter),
            )
            family.ecs_service.lbs.append(service_lb)
            add_parameters(family.template, [ELB_GRACE_PERIOD])
            family.ecs_service.ecs_service.HealthCheckGracePeriodSeconds = Ref(
                ELB_GRACE_PERIOD
            )
            handle_sg_lb_ingress_to_service(self.elbv2, family, self.elbv2.stack)
