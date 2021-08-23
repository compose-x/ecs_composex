#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re
from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.vpc.vpc_params import SG_ID_TYPE

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)


FS_REGEXP = re.compile(
    r"^(arn:aws[-a-z]*:elasticfilesystem:[0-9a-z-:]+:file-system/fs-[0-9a-f]{8,40}|fs-[0-9a-f]{8,40})$"
)


FS_ID_T = "FilesystemId"
FS_ID = Parameter(
    FS_ID_T,
    Type="String",
    AllowedPattern=FS_REGEXP.pattern,
)

FS_PORT_T = "FilesystemPort"
FS_PORT = Parameter(
    FS_PORT_T, Type="Number", MinValue=1, MaxValue=((2 ** 16) - 1), Default=2049
)

FS_ARN_T = "FilesystemArn"
FS_ARN = Parameter(FS_ARN_T, return_value="Arn", Type="String")

FS_AS_ID_T = "EfsAccessPointId"
FS_AS_ID = Parameter(FS_AS_ID_T, Type="String")

FS_MNT_PT_SG_ID_T = "FilesystemMountPointSgId"
FS_MNT_PT_SG_ID = Parameter(FS_MNT_PT_SG_ID_T, return_value="GroupId", Type=SG_ID_TYPE)
