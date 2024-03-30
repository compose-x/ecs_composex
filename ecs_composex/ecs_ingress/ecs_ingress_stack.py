#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@compose-x.io>

"""

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily

from troposphere import FindInMap, GetAtt, Output, Ref, Sub, Tags
from troposphere.ec2 import SecurityGroup

from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
    build_template,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.vpc.vpc_params import VPC_ID
from ecs_composex.vpc.vpc_stack import XStack as VpcStack


class ServiceSecurityGroup:

    def __init__(self, family: ComposeFamily, sgs_stack: XStack):
        self.family = family
        self.stack: XStack = sgs_stack
        cfn_resource = SecurityGroup(
            f"{family.logical_name}SG",
            GroupDescription=Sub(
                f"SG for {family.logical_name} in ${{ROOT_STACK}}",
                ROOT_STACK=define_stack_name(sgs_stack.stack_template),
            ),
            VpcId=Ref(VPC_ID),
            Tags=Tags(
                {
                    "Name": Sub(
                        f"${family.logical_name}-${{STACK_NAME}}",
                        STACK_NAME=define_stack_name(),
                    ),
                    "compose-x:family-name": family.name,
                    "compose-x:family-logical-name": family.logical_name,
                }
            ),
        )
        self.cfn_resource = add_resource(sgs_stack.stack_template, cfn_resource)
        self.output = Output(
            self.cfn_resource.title, Value=GetAtt(self.cfn_resource, "GroupId")
        )
        self.parameter = Parameter(
            self.cfn_resource.title,
            return_value="GroupId",
            group_label="Networking",
            label="Service to Service Security Group ID",
            Type="AWS::EC2::SecurityGroup::Id",
        )


class XStack(ComposeXStack):
    """
    Class to represent the IAM top stack
    """

    def __init__(self, name: str, settings: ComposeXSettings, **kwargs):
        stack_template = build_template(
            "Services SG for service-to-service communication"
        )
        self.services_mappings: dict[str, ServiceSecurityGroup] = {}
        add_parameters(stack_template, [CLUSTER_NAME, VPC_ID])
        super().__init__(name, stack_template, **kwargs)

        for family in settings.families.values():
            sg = ServiceSecurityGroup(family, self)
            self.services_mappings[family.name] = sg
            add_outputs(stack_template, [sg.output])

    def update_vpc_settings(self, vpc_stack: VpcStack):
        if vpc_stack.vpc_resource and (
            vpc_stack.vpc_resource.cfn_resource or vpc_stack.vpc_resource.mappings
        ):
            if vpc_stack.vpc_resource.cfn_resource:
                self.Parameters[VPC_ID.title] = GetAtt(
                    vpc_stack.title, f"Outputs.{VPC_ID.title}"
                )
            else:
                self.Parameters.update(
                    {VPC_ID.title: FindInMap("Network", VPC_ID.title, VPC_ID.title)}
                )
