﻿#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@compose-x.io>
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

from os import path
from ecs_composex.ecs_composex import X_KEY
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.vpc.vpc_params import SG_ID_TYPE


MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"

LB_ID_T = "elbv2Id"
LB_ARN_T = "elbv2Arn"
LB_SG_ID_T = "elbv2SecurityGroupId"
LB_DNS_NAME_T = "DNSName"
LB_DNS_ZONE_ID_T = "CanonicalHostedZoneID"

LB_ID = Parameter(LB_ID_T, Type="String")
LB_ARN = Parameter(LB_ARN_T, Type="String")
LB_SG_ID = Parameter(LB_SG_ID_T, return_value="GroupId", Type=SG_ID_TYPE)
LB_DNS_NAME = Parameter(LB_DNS_NAME_T, return_value="DNSName", Type="String")
LB_DNS_ZONE_ID = Parameter(
    LB_DNS_ZONE_ID_T,
    return_value="CanonicalHostedZoneID",
    Type="String",
    AllowedPattern=r"^Z[0-9A-Z]+$",
)
LB_NAME_T = "LoadBalancerName"
LB_NAME = Parameter(LB_NAME_T, return_value="LoadBalancerName", Type="String")
LB_FULL_NAME_T = "LoadBalancerFullName"
LB_FULL_NAME = Parameter(
    LB_FULL_NAME_T, return_value="LoadBalancerFullName", Type="String"
)
LB_SGS_IDS_T = "LBSecurityGroups"
LB_SGS_IDS = Parameter(
    LB_SGS_IDS_T,
    return_value="SecurityGroups",
    Type="List<AWS::EC2::SecurityGroup::Id>",
)

TGT_GROUP_ARN_T = "TargetGroupArn"
TGT_GROUP_ARN = Parameter(TGT_GROUP_ARN_T, Type="String")

TGT_GROUP_NAME_T = "TargetGroupName"
TGT_GROUP_NAME = Parameter(
    TGT_GROUP_NAME_T, return_value="TargetGroupName", Type="String"
)
