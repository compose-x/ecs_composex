#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

import json
from os import path

import yaml
from compose_x_common.compose_x_common import keyisset
from troposphere import Sub
from troposphere.ssm import Parameter as SSMParameter

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper as Dumper
    from yaml import Loader as Loader

from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_prometheus.emf_processors import generate_emf_processors


def set_cw_prometheus_config_parameter(
    family: ComposeFamily, options: dict
) -> SSMParameter:
    """
    Function to add the SSM Parameter representing the Prometheus scrapper config

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param dict options:
    :return: parameter
    :rtype: troposphere.ssm.Parameter
    """
    scrape_config = {}
    if keyisset("ScrapingConfiguration", options):
        scrape_config = options["ScrapingConfiguration"]
    if keyisset("ScrapingConfigurationFile", scrape_config):
        with open(
            path.abspath(scrape_config["ScrapingConfigurationFile"])
        ) as config_fd:
            value_py = yaml.load(config_fd.read(), Loader=Loader)
    else:
        value_py = {
            "global": {
                "scrape_interval": "1m"
                if not keyisset("Interval", scrape_config)
                else scrape_config["Interval"],
                "scrape_timeout": "10s"
                if not keyisset("Timeout", scrape_config)
                else scrape_config["Timeout"],
            },
            "scrape_configs": [
                {
                    "job_name": "${STACK_SHORT_ID}-cwagent-ecs-file-sd-config",
                    "sample_limit": 10000,
                    "file_sd_configs": [{"files": ["/tmp/cwagent_ecs_auto_sd.yaml"]}],
                }
            ],
        }

    parameter = SSMParameter(
        f"{family.logical_name}SSMPrometheusConfig",
        Tier="Standard",
        Type="String",
        Name=Sub(
            f"/ecs/config/prometheus/${{{ecs_params.CLUSTER_NAME.title}}}/${{STACK_SHORT_ID}}"
            f"/${{{ecs_params.SERVICE_NAME_T}}}",
            STACK_SHORT_ID=STACK_ID_SHORT,
        ),
        Description=Sub(
            f"Prometheus Scraping SSM Parameter for ECS Cluster: ${{{ecs_params.CLUSTER_NAME.title}}}"
        ),
        Value=Sub(yaml.dump(value_py, Dumper=Dumper), STACK_SHORT_ID=STACK_ID_SHORT),
    )
    if parameter.title not in family.template.resources:
        family.template.add_resource(parameter)
        return parameter
    else:
        return family.template.resources[parameter.title]


def set_cw_config_parameter(
    family: ComposeFamily, enable_emf: bool = False, **prometheus_options
) -> SSMParameter:
    """
    Function to add the SSM Parameter representing the Prometheus scrapper config
    """

    prometheus_collection = {
        "prometheus_config_path": "env:PROMETHEUS_CONFIG_CONTENT",
        "emf_processor": {
            "metric_declaration": [],
        },
    }
    value_py = {
        "logs": {
            "metrics_collected": {},
            "force_flush_interval": 15,
        }
    }
    if enable_emf:
        value_py["logs"]["metrics_collected"]["emf"]: dict = {}
    if keyisset("EnableCWAgentDebug", prometheus_options):
        value_py["agent"] = {"debug": True}
    if any(prometheus_options.values()) and prometheus_options.values():
        value_py["logs"]["metrics_collected"]["prometheus"] = prometheus_collection
        ecs_sd_config = {
            "sd_frequency": "1m",
            "sd_result_file": "/tmp/cwagent_ecs_auto_sd.yaml",
            "docker_label": {},
            "task_definition_list": [],
            "service_name_list_for_tasks": [],
        }
        value_py["logs"]["metrics_collected"]["prometheus"][
            "ecs_service_discovery"
        ] = ecs_sd_config
        emf_processors = generate_emf_processors(
            family, ecs_sd_config, **prometheus_options
        )
        value_py["logs"]["metrics_collected"]["prometheus"][
            "emf_processor"
        ] = emf_processors
    parameter = SSMParameter(
        f"{family.logical_name}SSMCWAgentPrometheusConfig",
        Tier="Intelligent-Tiering",
        Type="String",
        Name=Sub(
            f"/ecs/config/cw_agent_config/${{{ecs_params.CLUSTER_NAME.title}}}/${{STACK_SHORT_ID}}"
            f"/${{{ecs_params.SERVICE_NAME_T}}}",
            STACK_SHORT_ID=STACK_ID_SHORT,
        ),
        Description=Sub(
            f"Prometheus Scraping SSM Parameter for ECS Cluster: ${{{ecs_params.CLUSTER_NAME.title}}}"
        ),
        Value=Sub(
            json.dumps(value_py, ensure_ascii=True, sort_keys=True, indent=2),
            STACK_SHORT_ID=STACK_ID_SHORT,
        ),
    )
    if parameter.title not in family.template.resources:
        family.template.add_resource(parameter)
        return parameter
    else:
        return family.template.resources[parameter.title]
