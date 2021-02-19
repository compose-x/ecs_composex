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

"""
Module to handle the creation of the root EFS stack
"""

from troposphere import Ref, GetAtt, Sub
from troposphere.ec2 import SecurityGroup
from troposphere.efs import FileSystem, MountTarget

from ecs_composex.common import build_template
from ecs_composex.resources_import import import_record_properties
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import XResource, set_resources

from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS

from ecs_composex.efs.efs_params import (
    MOD_KEY,
    RES_KEY,
    FS_ID,
    FS_AS_ID,
    FS_MNT_PT_SG_ID,
)


def create_efs_stack(settings, new_resources):
    """
    Function to create the root stack and add EFS FS.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list new_resources:
    :return: Root template for EFS
    :rtype: troposphere.Template
    """
    template = build_template("Root for EFS built by ECS Compose-X")
    for res in new_resources:
        res_cfn_props = import_record_properties(res.properties, FileSystem)
        print(res_cfn_props)
        res.cfn_resource = FileSystem(res.logical_name, **res_cfn_props)
        res.sg = SecurityGroup(
            f"{res.logical_name}SecurityGroup",
            GroupName=Sub(f"{res.logical_name}EfsSg"),
            GroupDescription=Sub(f"SG for EFS {res.cfn_resource.title}"),
        )
        template.add_resource(res.cfn_resource)
        template.add_resource(res.sg)
        res.init_outputs()
        res.generate_outputs()
        template.add_output(res.outputs)
    return template


class Efs(XResource):
    """
    Class to represent a Filesystem
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(self, name, definition, settings):
        print("EFS", name, definition)
        self.sg = None
        self.mnt_targets = []
        self.volume = definition["Volume"]
        super().__init__(name, definition, settings)
        self.set_override_subnets()

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            FS_ID.title: (self.logical_name, self.cfn_resource, Ref, None),
            self.sg.title: (
                self.sg.title,
                self.sg,
                GetAtt,
                "GroupId",
            ),
        }


class XStack(ComposeXStack):
    """
    Class to represent the root for EFS
    """

    def __init__(self, name, settings, **kwargs):
        set_resources(settings, Efs, RES_KEY)
        print(settings.compose_content[RES_KEY])
        new_resources = [
            settings.compose_content[RES_KEY][resource]
            for resource in settings.compose_content[RES_KEY].keys()
            if not settings.compose_content[RES_KEY][resource].lookup
            and settings.compose_content[RES_KEY][resource].properties
        ]
        if new_resources:
            stack_template = create_efs_stack(settings, new_resources)
            super().__init__(name, stack_template, **kwargs)
        else:
            self.is_void = True
