﻿#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage the creation of Dashboards
"""

import json

from troposphere import GetAtt, Output, Parameter, Ref, Sub
from troposphere.cloudwatch import Dashboard as CWDashboard

from ecs_composex.common import (
    LOG,
    NONALPHANUM,
    add_outputs,
    add_parameters,
    build_template,
    keyisset,
    keypresent,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dashboards.dashboards_params import DASHBOARD_NAME, MOD_KEY, RES_KEY
from ecs_composex.dashboards.dashboards_services_metrics import ServiceEcsWidget
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, SERVICE_T


def retrieve_services(settings, services, x_stack):
    """
    Function to
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param dict services:
    :param ecs_composex.common.stacks.ComposeXStack x_stack:
    :return:
    """
    services_params = []
    for name, service_def in services.items():
        if name not in settings.families.keys():
            LOG.warn(f"Service family {name} is not defined. Skipping")
            continue
        family = settings.families[name]
        s_param = Parameter(f"{family.stack.title}{SERVICE_T}", Type="String")
        if SERVICE_T not in family.template.outputs:
            add_outputs(family.template, [Output(s_param.title, Value=Ref(SERVICE_T))])
        x_stack.Parameters.update(
            {s_param.title: GetAtt(family.stack.title, f"Outputs.{s_param.title}")}
        )
        services_params.append((family.stack.title, s_param))
    add_parameters(x_stack.stack_template, [value[1] for value in services_params])
    return services_params


def create_dashboards(settings, x_stack):
    """
    Loop to iterate over dashboards definitions

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack x_stack:
    """
    if not keyisset(RES_KEY, settings.compose_content):
        LOG.error(f"No {RES_KEY} defined")
    dashboards = settings.compose_content[RES_KEY]
    for name, dashboard in dashboards.items():
        widgets = []
        if keyisset("Services", dashboard):
            service_params = retrieve_services(settings, dashboard["Services"], x_stack)
            y_index = 0
            for param in service_params:
                service_ecs_widgets = ServiceEcsWidget(
                    param[0], param[1], CLUSTER_NAME, y_index=y_index
                )
                widgets += service_ecs_widgets.widgets
                y_index += service_ecs_widgets.height + 1
        dashboard_body_header = {"start": "-PT12H", "widgets": widgets}
        dashboard_body = Sub(json.dumps(dashboard_body_header))
        cfn_dashboard = CWDashboard(
            NONALPHANUM.sub("", name), DashboardBody=dashboard_body, DashboardName=name
        )
        x_stack.stack_template.add_resource(cfn_dashboard)


class XStack(ComposeXStack):
    """
    Class to manage the Dashboard stack
    """

    def __init__(self, title, settings, **kwargs):
        stack_template = build_template("Root template for Dashboards", [CLUSTER_NAME])
        super().__init__(title, stack_template, **kwargs)
        create_dashboards(settings, self)
