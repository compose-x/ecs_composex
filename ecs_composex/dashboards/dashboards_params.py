#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.cfn_params import Parameter

DASHBOARD_NAME_T = "DashboardName"
DASHBOARD_NAME = Parameter(DASHBOARD_NAME_T, Type="String")
