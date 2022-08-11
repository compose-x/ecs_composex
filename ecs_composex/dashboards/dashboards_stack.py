#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage the creation of Dashboards
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.ecs.ecs_family import ComposeFamily

import json

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Output, Parameter, Sub
from troposphere.cloudwatch import Dashboard as CWDashboard

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    build_template,
)
from ecs_composex.dashboards.dashboards_services_metrics import ServiceEcsWidget
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, SERVICE_T


def get_family_from_name(settings: ComposeXSettings, name: str) -> ComposeFamily | None:
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param name:
    """
    for family in settings.families.values():
        if family.name == name:
            return family
    return None


def retrieve_services(
    settings: ComposeXSettings, services: dict, x_stack: ComposeXStack
) -> list[tuple]:
    """
    Function to

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param dict services:
    :param ecs_composex.common.stacks.ComposeXStack x_stack:
    :return:
    """
    services_params = []
    families_original_names = [f.name for f in settings.families.values()]
    for name, service_def in services.items():
        if name not in families_original_names:
            LOG.warn(f"Service family {name} is not defined. Skipping")
            continue
        family = get_family_from_name(settings, name)
        if family is None:
            LOG.warn(
                f"Could not identify the {name} family in {families_original_names}"
            )
            continue
        s_param = Parameter(f"{family.stack.title}{SERVICE_T}Name", Type="String")
        if SERVICE_T not in family.template.outputs:
            add_outputs(
                family.template,
                [Output(s_param.title, Value=GetAtt(SERVICE_T, "Name"))],
            )
        x_stack.Parameters.update(
            {s_param.title: GetAtt(family.stack.title, f"Outputs.{s_param.title}")}
        )
        services_params.append((family.stack.title, s_param))
    add_parameters(x_stack.stack_template, [value[1] for value in services_params])
    return services_params


def create_dashboards(
    settings: ComposeXSettings, x_stack: ComposeXStack, module: XResourceModule
) -> None:
    """
    Loop to iterate over dashboards definitions

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack x_stack:
    :param ModManager module:
    """
    if not keyisset(module.res_key, settings.compose_content):
        LOG.error(f"No {module.res_key} defined")
    dashboards = settings.compose_content[module.res_key]
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
            NONALPHANUM.sub("", name),
            DashboardBody=dashboard_body,
            DashboardName=Sub(
                f"${{StackName}}--{name}",
                StackName=define_stack_name(x_stack.template),
            ),
        )
        x_stack.stack_template.add_resource(cfn_dashboard)


class XStack(ComposeXStack):
    """
    Class to manage the Dashboard stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        params = {
            CLUSTER_NAME.title: settings.ecs_cluster,
        }
        stack_template = build_template("Root template for Dashboards", [CLUSTER_NAME])
        super().__init__(title, stack_template, stack_parameters=params, **kwargs)
        create_dashboards(settings, self, module)
