# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle the creation of the root EFS stack
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

import warnings

from troposphere import GetAtt, Ref, Select, Sub
from troposphere.ec2 import SecurityGroup
from troposphere.efs import FileSystem, MountTarget

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.compose.x_resources.network_x_resources import NetworkXResource
from ecs_composex.efs.efs_params import FS_ARN, FS_ID, FS_MNT_PT_SG_ID, FS_PORT
from ecs_composex.resources_import import import_record_properties
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID


def create_efs_stack(settings, new_resources):
    """
    Function to create the root stack and add EFS FS.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list new_resources:
    :return: Root template for EFS
    :rtype: troposphere.Template
    """
    template = build_template("Root for EFS built by ECS Compose-X", [FS_PORT])
    for res in new_resources:
        res_cfn_props = import_record_properties(res.properties, FileSystem)
        res.cfn_resource = FileSystem(res.logical_name, **res_cfn_props)
        res.db_sg = SecurityGroup(
            f"{res.logical_name}SecurityGroup",
            GroupName=Sub(f"{res.logical_name}EfsSg"),
            GroupDescription=Sub(f"SG for EFS {res.cfn_resource.title}"),
            VpcId=Ref(VPC_ID),
        )
        template.add_resource(res.cfn_resource)
        template.add_resource(res.db_sg)
        res.init_outputs()
        res.generate_outputs()
        template.add_output(res.outputs)
    return template


class Efs(NetworkXResource):
    """
    Class to represent a Filesystem
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        self.db_sg = None
        self.db_secret = None
        self.mnt_targets = []
        self.access_points = []
        self.volume = definition["Volume"]
        super().__init__(name, definition, module, settings)
        self.support_defaults = True
        self.set_override_subnets()
        self.ref_parameter = FS_ID
        self.arn_parameter = FS_ARN
        self.security_group_param = FS_MNT_PT_SG_ID
        self.port_param = FS_PORT

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            FS_ID: (self.logical_name, self.cfn_resource, Ref, None),
            FS_ARN: (
                f"{self.logical_name}{FS_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                FS_ARN.return_value,
            ),
            FS_PORT: (
                f"{self.logical_name}{FS_PORT.title}",
                None,
                FS_PORT.Default,
                False,
            ),
            FS_MNT_PT_SG_ID: (
                f"{self.logical_name}{FS_MNT_PT_SG_ID.return_value}",
                self.db_sg,
                GetAtt,
                FS_MNT_PT_SG_ID.return_value,
            ),
        }

    def update_from_vpc(self, vpc_stack, settings=None):
        """
        Override for EFS to update settings from VPC Stack

        :param ecs_composex.vpc.vpc_stack.XStack vpc_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        subnets_params = self.subnets_param
        if self.subnets_override:
            for subnet_az in vpc_stack.vpc_resource.azs:
                if subnet_az.title == self.subnets_override:
                    subnets_params = subnet_az
                    break
            else:
                raise KeyError(
                    f"{self.module.res_key}.{self.name} - "
                    f"Override subnet name {self.subnets_override} is not defined in x-vpc",
                    list(vpc_stack.vpc_resource.azs.keys()),
                )
        for count, az in enumerate(vpc_stack.vpc_resource.azs[subnets_params]):
            self.stack.stack_template.add_resource(
                MountTarget(
                    f"{self.logical_name}MountPoint{az.title().strip().split('-')[-1]}",
                    FileSystemId=Ref(self.cfn_resource),
                    SecurityGroups=[GetAtt(self.db_sg, "GroupId")],
                    SubnetId=Select(count, Ref(STORAGE_SUBNETS)),
                )
            )


class XStack(ComposeXStack):
    """
    Class to represent the root for EFS
    """

    def __init__(
        self, name, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.new_resources:
            stack_template = create_efs_stack(settings, module.new_resources)
            super().__init__(name, stack_template, **kwargs)
        else:
            self.is_void = True
        if module.lookup_resources:
            warnings.warn(
                f"{module.res_key} - Lookup not supported. You can only create new resources at the moment"
            )
        for resource in module.resources_list:
            resource.stack = self
