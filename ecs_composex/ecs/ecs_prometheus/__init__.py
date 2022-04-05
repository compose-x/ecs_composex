#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.compose.compose_services import ComposeService
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

    insights_options = {
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
                family, service, prometheus_config, insights_options
            )
    if any(insights_options.values()):
        add_cw_agent_to_family(family, **insights_options)


def add_cw_agent_to_family(family, **options):
    """
    Function to add the CW Agent to the task family for additional monitoring
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    """
    prometheus_config = set_cw_prometheus_config_parameter(family, options)
    cw_agent_config = set_cw_config_parameter(family, **options)
    cw_agent_service = define_cloudwatch_agent(prometheus_config, cw_agent_config)
    cw_agent_service.add_to_family(family)
    set_ecs_cw_policy(family, prometheus_config, cw_agent_config)
