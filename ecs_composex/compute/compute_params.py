#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Cluster parameters for CFN
This is a crucial part as all the titles, maked `_T` are string which are then used the same way
across all imports, which gives consistency for CFN to use the same names,
which it heavily relies onto.

You can change the names *values* so you like so long as you keep it [a-zA-Z0-9]
"""

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T

HOST_ROLE_T = "EcsHostsRole"
HOST_PROFILE_T = "EcsHostsInstanceProfile"
NODES_SG_T = "EcsHostsSg"

CLUSTER_NAME = Parameter(CLUSTER_NAME_T, Type="String")

ECS_AMI_ID_T = "EcsAmiId"
ECS_AMI_ID = Parameter(
    ECS_AMI_ID_T,
    Type="AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
    Default="/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id",
)

MAX_CAPACITY_T = "EcsMaxCapacity"
MAX_CAPACITY = Parameter(MAX_CAPACITY_T, Type="Number", Default=1)

MIN_CAPACITY_T = "EcsMinCapacity"
MIN_CAPACITY = Parameter(MIN_CAPACITY_T, Type="Number", MinValue=1, Default=1)

TARGET_CAPACITY_T = "EcsTargetCapacity"
TARGET_CAPACITY = Parameter(
    TARGET_CAPACITY_T, Type="Number", Default=MIN_CAPACITY.Default
)

LAUNCH_TEMPLATE_ID_T = "LaunchTemplateId"
LAUNCH_TEMPLATE_ID = Parameter(
    LAUNCH_TEMPLATE_ID_T, Type="String", Description="ID Of the Launch Template"
)

LAUNCH_TEMPLATE_VersionNumber_T = "LaunchTemplateVersionNumber"
LAUNCH_TEMPLATE_VersionNumber = Parameter(
    LAUNCH_TEMPLATE_VersionNumber_T,
    Type="Number",
    Description="VersionNumber Of the Launch Template",
)
