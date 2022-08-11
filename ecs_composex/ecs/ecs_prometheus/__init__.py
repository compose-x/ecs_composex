#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from compose_x_common.compose_x_common import keyisset
from troposphere import If
from troposphere.ecs import Environment

from ecs_composex.common.logging import LOG
from ecs_composex.compose.compose_services import ComposeService
from ecs_composex.compose.compose_services.helpers import extend_container_envvars
from ecs_composex.ecs.ecs_conditions import USE_BRIDGE_NETWORKING_MODE_CON_T
from ecs_composex.ecs.ecs_prometheus.config_ssm_parameters import (
    set_cw_config_parameter,
    set_cw_prometheus_config_parameter,
)
from ecs_composex.ecs.ecs_prometheus.helpers import (
    define_cloudwatch_agent,
    set_ecs_cw_policy,
)


def set_prometheus_containers_insights(
    family, service: ComposeService, prometheus_config: dict, insights_options: dict
):
    """
    Sets prometheus configuration to export to ECS Containers Insights
    """
    if keyisset("ContainersInsights", prometheus_config):
        config = service.definition["x-prometheus"]["ContainersInsights"]
        for key in insights_options.keys():
            if keyisset(key, config):
                insights_options[key] = config[key]
        if keyisset("CustomRules", config):
            insights_options["CustomRules"] = config["CustomRules"]
            LOG.info(
                f"{family.name} - Prometheus CustomRules options set for {service.name}"
            )


def set_prometheus(family):
    """
    Reviews services config
    :return:
    """

    prometheus_options = {
        "CollectForAppMesh": False,
        "CollectForJavaJmx": False,
        "CollectForNginx": False,
        "EnableTasksDiscovery": False,
        "EnableCWAgentDebug": False,
        "AutoAddNginxPrometheusExporter": False,
        "ScrapingConfiguration": False,
    }
    for service in family.services:
        if keyisset("x-prometheus", service.definition):
            prometheus_config = service.definition["x-prometheus"]
            set_prometheus_containers_insights(
                family, service, prometheus_config, prometheus_options
            )

    for service in family.services:
        if keyisset("x-monitoring", service.definition) and keyisset(
            "CWAgentCollectEmf", service.definition["x-monitoring"]
        ):
            collect_emf = True
            break
    else:
        collect_emf = False

    if any(prometheus_options.values()):
        add_cw_agent_to_family(family, collect_emf, **prometheus_options)
    else:
        add_cw_agent_to_family(family, collect_emf)


def add_cw_agent_to_family(
    family: ComposeFamily, collect_emf: bool = False, **prometheus_options
):
    """
    Function to add the CW Agent to the task family for additional monitoring
    """
    if not collect_emf and not prometheus_options:
        return
    if prometheus_options:
        prometheus_config = set_cw_prometheus_config_parameter(
            family, prometheus_options
        )
    else:
        prometheus_config = None
    cw_agent_config = set_cw_config_parameter(family, collect_emf, **prometheus_options)
    cw_agent_service = define_cloudwatch_agent(prometheus_config, cw_agent_config)
    cw_agent_service.add_to_family(family, is_dependency=True)
    set_ecs_cw_policy(family, prometheus_config, cw_agent_config)
    family.cwagent_service = cw_agent_service
    if collect_emf:
        env_var = Environment(
            Name="AWS_EMF_AGENT_ENDPOINT",
            Value=If(
                USE_BRIDGE_NETWORKING_MODE_CON_T,
                "tcp://cwagent:25888",
                "tcp://127.0.0.1:25888",
            ),
        )
        for service in family.services:
            if service is cw_agent_service:
                continue
            extend_container_envvars(service.container_definition, [env_var])
        LOG.info(
            f"services.{family.name} - Granting AWSLambdaBasicExecutionRole Policy for EMF"
        )
        family.iam_manager.add_new_managed_policy(
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            role_name=family.iam_manager.task_role._role_type,
        )
