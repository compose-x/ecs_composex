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
Module to define the EFS Root template and potential nested stacks
"""

from troposphere import AWS_NO_VALUE, AWS_STACK_NAME
from troposphere import Ref, GetAtt, If, Sub, Select
from troposphere import efs, Tags
from troposphere.ec2 import SecurityGroup

from ecs_composex.common import keyisset, build_template, LOG
from ecs_composex.common.compose_resources import XResource
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID
from ecs_composex.efs.efs_params import RES_KEY, EFS_ARN, EFS_ID, EFS_SG_ID_T

MAX_OUTPUTS = 50


class Efs(XResource):
    """
    Class for AWS EFS
    """

    default_properties = {
        "Encrypted": True,
        "ThroughputMode": "bursting",
        "PerformanceMode": "generalPurpose",
    }
    output_per_fs = 2

    def __init__(self, name, definition):
        self.security_group = None
        super().__init__(name, definition)

    def define_tags(self, props):
        """
        Method to define the tags correctly
        :param props:
        :return:
        """
        prop_name = "FileSystemTags"
        if not keyisset(prop_name, self.properties):
            props[prop_name] = Ref(AWS_NO_VALUE)
            return
        tags = self.properties[prop_name]
        t_tags = Tags()
        for tag in tags:
            if keyisset("Key", tag) and keyisset("Value", tag):
                t_tags += Tags({tag["Key"]: tag["Value"]})
            else:
                LOG.warn(f"Misformatted tag {tag}. Expected Key/Value combination.")
        props[prop_name] = t_tags

    def define_backup_policy(self, props):
        """
        Method to define backup policy

        :param dict props:
        """
        prop_name = "BackupPolicy"
        if not keyisset(prop_name, self.properties):
            props[prop_name] = Ref(AWS_NO_VALUE)
        elif keyisset(prop_name, self.properties):
            if keyisset("Status", self.properties[prop_name]):
                policy = efs.BackupPolicy(Status=self.properties[prop_name]["Status"])
                props[prop_name] = policy
            else:
                LOG.warn(
                    f"{prop_name} is defined but Status is not set. Defaulting to NoValue"
                )
                props[prop_name] = Ref(AWS_NO_VALUE)

    def define_lifecycle_policy(self, props):
        """
        Method to define the lifecycle policy.

        :param dict props:
        :return:
        """
        prop_name = "LifecyclePolicies"
        if not keyisset(prop_name, self.properties):
            props[prop_name] = Ref(AWS_NO_VALUE)
            return
        policies = self.properties[prop_name]
        cfn_policies = []
        for policy in policies:
            if not keyisset("TransitionToIA", policy):
                raise KeyError("Lifecycle policies must have TransitionToIA defined")
            cfn_policies.append(
                efs.LifecyclePolicy(TransitionToIA=policy["TransitionToIA"])
            )
        props[prop_name] = cfn_policies

    def add_mount_points(self, template, settings):
        """
        Method to add mountpoints in VPC.

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param troposphere.Template template:
        :return:
        """
        self.security_group = SecurityGroup(
            f"{self.logical_name}{EFS_SG_ID_T}",
            template=template,
            GroupName=If(
                USE_STACK_NAME_CON_T,
                Sub(f"efs-{self.logical_name}-${{{AWS_STACK_NAME}}}"),
                Sub(f"efs-${self.logical_name}-${{{ROOT_STACK_NAME.title}}}"),
            ),
            GroupDescription=Sub(f"SG for EFS FS ${self.cfn_resource}"),
            VpcId=Ref(VPC_ID)
        )
        iter_list = settings.storage_subnets if settings.storage_subnets else settings.aws_azs
        for count, az in enumerate(iter_list):
            efs.MountTarget(
                f"{self.logical_name}MountPoint{count}",
                template=template,
                FileSystemId=Ref(self.cfn_resource),
                SecurityGroups=[Ref(self.security_group)],
                SubnetId=Select(count, Ref(STORAGE_SUBNETS))
            )

    def define_fs(self):
        """
        Method to define the EFS FileSystem
        """
        if not self.properties:
            self.properties = self.default_properties
        props = {}
        props.update(self.properties)
        self.define_backup_policy(props)
        self.define_tags(props)
        self.define_lifecycle_policy(props)
        self.cfn_resource = efs.FileSystem(self.logical_name, **props)


def create_efs_template(settings):
    """
    Function to create the EFS Root stack template

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    mono_template = True
    x_resources = settings.compose_content[RES_KEY]
    new_fses = [
        x_resources[res_name]
        for res_name in x_resources
        if not x_resources[res_name].lookup
    ]
    if len(new_fses) * Efs.output_per_fs >= MAX_OUTPUTS:
        mono_template = False
    root_template = build_template(f"Root template for {RES_KEY}")
    for fs in new_fses:
        fs.define_fs()
        values = [
            (EFS_ARN.title, "Arn", GetAtt(fs.cfn_resource, "Arn")),
            (EFS_ID.title, "Name", GetAtt(fs.cfn_resource, "FileSystemId"))
        ]
        if mono_template:
            root_template.add_resource(fs.cfn_resource)
            fs.add_mount_points(root_template, settings)
            values.append((EFS_SG_ID_T, EFS_SG_ID_T, Ref(fs.security_group)))
            outputs = ComposeXOutput(fs.cfn_resource, values, True)
            root_template.add_output(outputs.outputs)
        elif not mono_template:
            fs_template = build_template(f"Template for FS {fs.name}")
            fs_template.add_resource(fs.cfn_resource)
            fs.add_mount_points(fs_template, settings)
            values.append((EFS_SG_ID_T, EFS_SG_ID_T, Ref(fs.security_group)))
            outputs = ComposeXOutput(fs.cfn_resource, values, True)
            fs_template.add_output(outputs.outputs)
            fs_stack = ComposeXStack(fs.logical_name, stack_template=fs_template)
            root_template.add_resource(fs_stack)
    return root_template
