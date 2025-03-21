#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

import re
from copy import deepcopy

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_STACK_NAME

from ecs_composex.ecs.ecs_params import SERVICE_NAME
from ecs_composex.ecs.managed_sidecars.nginx_prometheus_exporter import (
    NGINX_EXPORTER_SERVICE,
)

METRICS_DEFAULT_PATH = r"/metrics"


def generate_ecs_sd_service_name_pattern(family: ComposeFamily) -> Union[str]:
    """
    Generate the ecs_service_discovery configuration for a given set of ECS Task Families
    """
    task_def_re = re.compile(
        r"(.*:task-definition/)|(arn:aws(?:[\S]+)?:ecs:[\S]+:\d{12}:task-definition/)"
    )
    if not task_def_re.match(family.name):
        task_name = f".*:task-definition/.*${{{SERVICE_NAME.title}}}"
    else:
        task_name = family.name
    return task_name


def get_ngnix_processor(
    family,
    ecs_sd_config,
    nginx_config,
):
    labels = (
        ["job"]
        if not keyisset("source_labels", nginx_config)
        else nginx_config["source_labels"]
    )
    default_matcher = (
        r"^.*nginx.*$"
        if not keyisset("label_matcher", nginx_config)
        else nginx_config["label_matcher"]
    )
    nginx_metrics = [
        {
            "source_labels": labels,
            "label_matcher": default_matcher,
            "dimensions": [["ClusterName", "TaskDefinitionFamily", "ServiceName"]],
            "metric_selectors": ["^nginx_.*$"],
        }
    ]
    ecs_sd_config["task_definition_list"].append(
        {
            "sd_job_name": "${STACK_SHORT_ID}-nginx-prometheus-exporter",
            "sd_metrics_path": (
                METRICS_DEFAULT_PATH
                if not keyisset("ExporterPath", nginx_config)
                else nginx_config["ExporterPath"]
            ),
            "sd_metrics_ports": (
                "9113"
                if not keyisset("ExporterPort", nginx_config)
                else str(nginx_config["ExporterPort"])
            ),
            "sd_task_definition_arn_pattern": generate_ecs_sd_service_name_pattern(
                family
            ),
        },
    )
    ecs_sd_config["service_name_list_for_tasks"].append(
        {
            "sd_job_name": "${STACK_SHORT_ID}-nginx-prometheus-exporter",
            "sd_metrics_path": (
                METRICS_DEFAULT_PATH
                if not keyisset("ExporterPath", nginx_config)
                else nginx_config["ExporterPath"]
            ),
            "sd_metrics_ports": (
                "9113"
                if not keyisset("ExporterPort", nginx_config)
                else str(nginx_config["ExporterPort"])
            ),
            "sd_service_name_pattern": f"^.*${{{AWS_STACK_NAME}}}.*$",
        }
    )
    return nginx_metrics


def get_jmx_processor(family, ecs_sd_config, jmx_config) -> list:
    labels = (
        ["job"]
        if not keyisset("source_labels", jmx_config)
        else jmx_config["source_labels"]
    )
    default_matcher = (
        r"^.*jmx.*$"
        if not keyisset("label_matcher", jmx_config)
        else jmx_config["label_matcher"]
    )
    jmx_metrics = [
        {
            "source_labels": labels,
            "label_matcher": default_matcher,
            "dimensions": [["ClusterName", "TaskDefinitionFamily"]],
            "metric_selectors": [
                "^jvm_threads_(current|daemon)$",
                "^jvm_classes_loaded$",
                "^java_lang_operatingsystem_(freephysicalmemorysize|totalphysicalmemorysize|freeswapspacesize"
                "|totalswapspacesize|systemcpuload|processcpuload|availableprocessors|openfiledescriptorcount)$",
                "^catalina_manager_(rejectedsessions|activesessions)$",
                "^jvm_gc_collection_seconds_(count|sum)$",
                "^catalina_globalrequestprocessor_(bytesreceived|bytessent|requestcount|errorcount|processingtime)$",
            ],
        },
        {
            "source_labels": labels,
            "label_matcher": default_matcher,
            "dimensions": [["ClusterName", "TaskDefinitionFamily", "area"]],
            "metric_selectors": ["^jvm_memory_bytes_used$"],
        },
        {
            "source_labels": labels,
            "label_matcher": default_matcher,
            "dimensions": [["ClusterName", "TaskDefinitionFamily", "pool"]],
            "metric_selectors": ["^jvm_memory_pool_bytes_used$"],
        },
    ]
    ecs_sd_config["task_definition_list"].append(
        {
            "sd_job_name": "${STACK_SHORT_ID}-javajmx-prometheus-exporter",
            "sd_metrics_path": (
                METRICS_DEFAULT_PATH
                if not keyisset("ExporterPath", jmx_config)
                else jmx_config["ExporterPath"]
            ),
            "sd_metrics_ports": (
                "9404"
                if not keyisset("ExporterPort", jmx_config)
                else str(jmx_config["ExporterPort"])
            ),
            "sd_task_definition_arn_pattern": generate_ecs_sd_service_name_pattern(
                family
            ),
        },
    )
    return jmx_metrics


def process_custom_rules(family, ecs_sd_config, options, emf_processors):
    """
    Func
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param dict ecs_sd_config:
    :param dict options:
    :param dict emf_processors:
    :return:
    """
    custom_rules = options["CustomRules"]
    for count, rule in enumerate(custom_rules):
        emf_processors["metric_declaration"] += rule["EmfProcessors"]
        ecs_sd_config["service_name_list_for_tasks"].append(
            {
                "sd_job_name": f"${{STACK_SHORT_ID}}-service-def-{family.logical_name}-custom-sd-{count}",
                "sd_metrics_path": (
                    METRICS_DEFAULT_PATH
                    if not keyisset("ExporterPath", rule)
                    else rule["ExporterPath"]
                ),
                "sd_metrics_ports": str(rule["ExporterPort"]),
                "sd_service_name_pattern": f"^.*${{{AWS_STACK_NAME}}}.*$",
            }
        )
        ecs_sd_config["task_definition_list"].append(
            {
                "sd_job_name": f"${{STACK_SHORT_ID}}-task-def-{family.logical_name}-custom-sd-{count}",
                "sd_metrics_path": (
                    METRICS_DEFAULT_PATH
                    if not keyisset("ExporterPath", rule)
                    else rule["ExporterPath"]
                ),
                "sd_metrics_ports": str(rule["ExporterPort"]),
                "sd_task_definition_arn_pattern": generate_ecs_sd_service_name_pattern(
                    family
                ),
            },
        )


def generate_emf_processors(family, ecs_sd_config, **options) -> dict:
    metrics_key = "metric_declaration"
    emf_processors = {
        "metric_declaration_dedup": True,
        metrics_key: [],
    }
    if keyisset("CollectForJavaJmx", options):
        emf_processors[metrics_key] += get_jmx_processor(
            family, ecs_sd_config, options["CollectForJavaJmx"]
        )
    if keyisset("CollectForNginx", options):
        emf_processors[metrics_key] += get_ngnix_processor(
            family, ecs_sd_config, options["CollectForNginx"]
        )
        if keyisset("AutoAddNginxPrometheusExporter", options):
            nginx_prom_exporter_service = deepcopy(NGINX_EXPORTER_SERVICE)
            nginx_prom_exporter_service.add_to_family(family)
    if keyisset("CustomRules", options):
        process_custom_rules(family, ecs_sd_config, options, emf_processors)
    return emf_processors
