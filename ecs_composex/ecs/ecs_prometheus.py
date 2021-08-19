#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to add Prometheus scraper for ECS tasks.
"""
import json
import re

import yaml

try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, AWS_STACK_NAME, Sub
from troposphere.ecs import Secret
from troposphere.iam import Policy
from troposphere.ssm import Parameter as SSMParameter

from ecs_composex.common import keyisset
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.compose_services import ComposeService
from ecs_composex.ecs import ecs_params

CW_IMAGE_PARAMETER = Parameter(
    "CloudwatchAgentImage",
    Type="String",
    Default="public.ecr.aws/cloudwatch-agent/cloudwatch-agent:latest",
)

NGINX_EXPORTER_IMAGE_PARAMETER = Parameter(
    "NginxPrometheusExporterImage",
    Type="String",
    Default="public.ecr.aws/compose-x/nginx-prometheus-exporter:0.9.0",
)

METRICS_DEFAULT_PATH = r"/metrics"


def set_cw_prometheus_config_parameter(family):
    """
    Function to add the SSM Parameter representing the Prometheus scrapper config
    :param ecs_composex.common.compose_services.ComposeFamily family:
    :return: parameter
    :rtype: troposphere.ssm.Parameter
    """
    value_py = {
        "global": {
            "scrape_interval": "1m",
            "scrape_timeout": "10s",
        },
        "scrape_configs": [
            {
                "job_name": "cwagent-ecs-file-sd-config",
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
            f"/ecs/config/prometheus/${{{ecs_params.CLUSTER_NAME.title}}}/${{{ecs_params.SERVICE_NAME_T}}}"
        ),
        Description=Sub(
            f"Prometheus Scraping SSM Parameter for ECS Cluster: ${{{ecs_params.CLUSTER_NAME.title}}}"
        ),
        Value=yaml.dump(value_py, Dumper=Dumper),
    )
    family.template.add_resource(parameter)
    return parameter


def generate_ecs_sd_service_name_pattern(family_name):
    """
    Generate the ecs_service_discovery configuration for a given set of set of ECS Task Families

    :param str family_name:
    :return:
    """
    task_def_re = re.compile(
        r"(.*:task-definition/)|(arn:aws(?:[\S]+)?:ecs:[\S]+:\d{12}:task-definition/)"
    )
    if not task_def_re.match(family_name):
        task_name = f".*:task-definition/.*{family_name}"
    else:
        task_name = family_name
    return task_name


def get_ecs_envoy_processor(envoy_container_name=None):
    """
    Function to return the envoy EMF configuration

    :param str envoy_container_name:
    :return:
    """
    if envoy_container_name is None:
        envoy_container_name = r"envoy"
    return [
        {
            "source_labels": ["container_name"],
            "label_matcher": f"^{envoy_container_name}$",
            "dimensions": [["ClusterName", "TaskDefinitionFamily"]],
            "metric_selectors": [
                "^envoy_http_downstream_rq_(total|xx)$",
                "^envoy_cluster_upstream_cx_(r|t)x_bytes_total$",
                "^envoy_cluster_membership_(healthy|total)$",
                "^envoy_server_memory_(allocated|heap_size)$",
                "^envoy_cluster_upstream_cx_(connect_timeout|destroy_local_with_active_rq)$",
                "^envoy_cluster_upstream_rq_(pending_failure_eject|"
                "pending_overflow|timeout|per_try_timeout|rx_reset|maintenance_mode)$",
                "^envoy_http_downstream_cx_destroy_remote_active_rq$",
                "^envoy_cluster_upstream_flow_control_(paused_reading_total|"
                "resumed_reading_total|backed_up_total|drained_total)$",
                "^envoy_cluster_upstream_rq_retry$",
                "^envoy_cluster_upstream_rq_retry_(success|overflow)$",
                "^envoy_server_(version|uptime|live)$",
            ],
        },
        {
            "source_labels": ["container_name"],
            "label_matcher": f"^{envoy_container_name}$",
            "dimensions": [
                [
                    "ClusterName",
                    "TaskDefinitionFamily",
                    "envoy_http_conn_manager_prefix",
                    "envoy_response_code_class",
                ]
            ],
            "metric_selectors": ["^envoy_http_downstream_rq_xx$"],
        },
    ]


def define_nginx_exporter_sidecar(family):
    """
    Function to define the NGINX Exporter sidecar

    :param ecs_composex.common.compose_services.ComposeFamily family:

    :return:
    """
    nginx_prom_exporter_agent_service_config = {
        "image": NGINX_EXPORTER_IMAGE_PARAMETER.Default,
        "deploy": {
            "resources": {"limits": {"cpus": 0.1, "memory": "64M"}},
            "labels": {"ecs.task.family": family.name},
        },
        "labels": {
            "container_name": "nginx-prometheus-exporter",
            "ECS_PROMETHEUS_EXPORTER_PORT": 9113,
            "job": "nginx-prometheus-exporter",
        },
        "ports": [{"target": 9113, "protocol": "tcp"}],
        "depends_on": [
            service.name for service in family.services if not service.is_aws_sidecar
        ],
    }
    nginx_prom_exporter_service = ComposeService(
        "nginx-prometheus-exporter", nginx_prom_exporter_agent_service_config
    )
    nginx_prom_exporter_service.is_aws_sidecar = True

    family.add_service(nginx_prom_exporter_service)
    family.refresh()


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
            "sd_job_name": "nginx-prometheus-exporter",
            "sd_metrics_path": METRICS_DEFAULT_PATH
            if not keyisset("ExporterPath", nginx_config)
            else nginx_config["ExporterPath"],
            "sd_metrics_ports": "9113"
            if not keyisset("ExporterPort", nginx_config)
            else str(nginx_config["ExporterPort"]),
            "sd_task_definition_arn_pattern": generate_ecs_sd_service_name_pattern(
                family.name
            ),
        },
    )
    ecs_sd_config["service_name_list_for_tasks"].append(
        {
            "sd_job_name": "nginx-prometheus-exporter",
            "sd_metrics_path": METRICS_DEFAULT_PATH
            if not keyisset("ExporterPath", nginx_config)
            else nginx_config["ExporterPath"],
            "sd_metrics_ports": "9113"
            if not keyisset("ExporterPort", nginx_config)
            else str(nginx_config["ExporterPort"]),
            "sd_service_name_pattern": f"^.*${{{AWS_STACK_NAME}}}.*$",
        }
    )
    return nginx_metrics


def get_jmx_processor(family, ecs_sd_config, jmx_config):
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
            "sd_job_name": "javajmx-prometheus-exporter",
            "sd_metrics_path": METRICS_DEFAULT_PATH
            if not keyisset("ExporterPath", jmx_config)
            else jmx_config["ExporterPath"],
            "sd_metrics_ports": "9404"
            if not keyisset("ExporterPort", jmx_config)
            else str(jmx_config["ExporterPort"]),
            "sd_task_definition_arn_pattern": generate_ecs_sd_service_name_pattern(
                family.name
            ),
        },
    )
    return jmx_metrics


def process_custom_rules(family, ecs_sd_config, options, emf_processors):
    """
    Func
    :param ecs_composex.common.compose_services.ComposeFamily family:
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
                "sd_job_name": f"service-def-{family.logical_name}-custom-sd-{count}",
                "sd_metrics_path": METRICS_DEFAULT_PATH
                if not keyisset("ExporterPath", rule)
                else rule["ExporterPath"],
                "sd_metrics_ports": str(rule["ExporterPort"]),
                "sd_service_name_pattern": f"^.*${{{AWS_STACK_NAME}}}.*$",
            }
        )
        ecs_sd_config["task_definition_list"].append(
            {
                "sd_job_name": f"task-def-{family.logical_name}-custom-sd-{count}",
                "sd_metrics_path": METRICS_DEFAULT_PATH
                if not keyisset("ExporterPath", rule)
                else rule["ExporterPath"],
                "sd_metrics_ports": str(rule["ExporterPort"]),
                "sd_task_definition_arn_pattern": generate_ecs_sd_service_name_pattern(
                    family.name
                ),
            },
        )


def generate_emf_processors(family, ecs_sd_config, **options):
    metrics_key = "metric_declaration"
    emf_processors = {
        "metric_declaration_dedup": True,
        metrics_key: [],
    }
    if keyisset("CollectForAppMesh", options):
        emf_processors[metrics_key] += get_ecs_envoy_processor()
    if keyisset("CollectForJavaJmx", options):
        emf_processors[metrics_key] += get_jmx_processor(
            family, ecs_sd_config, options["CollectForJavaJmx"]
        )
    if keyisset("CollectForNginx", options):
        emf_processors[metrics_key] += get_ngnix_processor(
            family, ecs_sd_config, options["CollectForNginx"]
        )
        if keyisset("AutoAddNginxPrometheusExporter", options):
            define_nginx_exporter_sidecar(family)
    if keyisset("CustomRules", options):
        process_custom_rules(family, ecs_sd_config, options, emf_processors)
    return emf_processors


def set_cw_config_parameter(family, **options):
    """
    Function to add the SSM Parameter representing the Prometheus scrapper config

    :param ecs_composex.common.compose_services.ComposeFamily family:
    :return: parameter
    :rtype: troposphere.ssm.Parameter
    """

    value_py = {
        "logs": {
            "metrics_collected": {
                "prometheus": {
                    "prometheus_config_path": "env:PROMETHEUS_CONFIG_CONTENT",
                    "emf_processor": {
                        "metric_declaration": [],
                    },
                }
            },
            "force_flush_interval": 5,
        }
    }
    if keyisset("EnableCWAgentDebug", options):
        value_py["agent"] = {"debug": True}
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
    if (
        keyisset("CollectForAppMesh", options)
        or keyisset("CollectForJavaJmx", options)
        or keyisset("CollectForNginx", options)
    ):
        emf_processors = generate_emf_processors(family, ecs_sd_config, **options)
        value_py["logs"]["metrics_collected"]["prometheus"][
            "emf_processor"
        ] = emf_processors
    parameter = SSMParameter(
        f"{family.logical_name}SSMCWAgentPrometheusConfig",
        Tier="Intelligent-Tiering",
        Type="String",
        Name=Sub(
            f"/ecs/config/cw_agent_config/${{{ecs_params.CLUSTER_NAME.title}}}/${{{ecs_params.SERVICE_NAME_T}}}"
        ),
        Description=Sub(
            f"Prometheus Scraping SSM Parameter for ECS Cluster: ${{{ecs_params.CLUSTER_NAME.title}}}"
        ),
        Value=Sub(json.dumps(value_py, ensure_ascii=True, sort_keys=True, indent=2)),
    )
    family.template.add_resource(parameter)
    return parameter


def define_cloudwatch_agent(family, cw_prometheus_config, cw_agent_config):
    """
    Function to define the CW Agent image task definition

    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param cw_prometheus_config:
    :param cw_agent_config:
    :return:
    """
    cw_agent_service_config = {
        "image": CW_IMAGE_PARAMETER.Default,
        "deploy": {
            "resources": {"limits": {"cpus": 0.1, "memory": "256M"}},
            "labels": {"ecs.task.family": family.name},
        },
        "labels": {"container_name": "cw-agent"},
        "depends_on": [
            service.name for service in family.services if not service.is_aws_sidecar
        ],
    }
    cw_service = ComposeService("cw_agent", cw_agent_service_config)
    cw_service.is_aws_sidecar = True
    secrets = [
        Secret(
            Name="PROMETHEUS_CONFIG_CONTENT",
            ValueFrom=Sub(
                f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                f":parameter${{{cw_prometheus_config.title}}}"
            ),
        ),
        Secret(
            Name="CW_CONFIG_CONTENT",
            ValueFrom=Sub(
                f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                f":parameter${{{cw_agent_config.title}}}"
            ),
        ),
    ]
    if hasattr(cw_service.container_definition, "Secrets"):
        s_secrets = getattr(cw_service.container_definition, "Secrets")
        s_secrets += secrets
    else:
        setattr(cw_service.container_definition, "Secrets", secrets)
    return cw_service


def set_ecs_cw_policy(prometheus_parameter, cw_config_parameter):
    """
    Renders the IAM policy to grant the TaskRole access to CW, ECS and SSM Parameters

    :param troposphere.ssm.Parameter prometheus_parameter:
    :param troposphere.ssm.Parameter cw_config_parameter:
    :return: The IAM policy
    :rtype: troposphere.iam.Policy
    """
    ecs_sd_policy = Policy(
        PolicyName="CWAgentAccessForPrometheusScraping",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EnableCreationAndManagementOfPrometheusLogEvents",
                    "Effect": "Allow",
                    "Action": ["logs:GetLogEvents", "logs:PutLogEvents"],
                    "Resource": Sub(
                        f"arn:${{{AWS_PARTITION}}}:logs:*:${{{AWS_ACCOUNT_ID}}}:"
                        "log-group:/aws/ecs/containerinsights/*:log-stream:*"
                    ),
                },
                {
                    "Sid": "EnableCreationAndManagementOfPrometheusCloudwatchLogGroupsAndStreams",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:DescribeLogStreams",
                        "logs:PutRetentionPolicy",
                        "logs:CreateLogGroup",
                    ],
                    "Resource": Sub(
                        f"arn:${{{AWS_PARTITION}}}:logs:*:${{{AWS_ACCOUNT_ID}}}:"
                        "log-group:/aws/ecs/containerinsights/*"
                    ),
                },
                {
                    "Sid": "ECSTaskDefinitionsAccess",
                    "Effect": "Allow",
                    "Action": ["ecs:DescribeTaskDefinition"],
                    "Resource": "*",
                },
                {
                    "Sid": "ServiceDiscoveryAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecs:DescribeTasks",
                        "ecs:ListTasks",
                        "ecs:DescribeContainerInstances",
                        "ecs:DescribeServices",
                        "ecs:ListServices",
                    ],
                    "Resource": "*",
                    "Condition": {
                        "ArnEquals": {
                            "ecs:cluster": Sub(
                                f"arn:${{{AWS_PARTITION}}}:ecs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                                f":cluster/${{{ecs_params.CLUSTER_NAME.title}}}"
                            )
                        }
                    },
                },
                {
                    "Sid": "ExtractFromCloudWatchAgentServerPolicy",
                    "Effect": "Allow",
                    "Action": ["ssm:GetParameter*"],
                    "Resource": [
                        Sub(
                            "arn:aws:ssm:*:${AWS::AccountId}:parameter/AmazonCloudWatch-*"
                        ),
                        Sub(
                            f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                            f":parameter${{{prometheus_parameter.title}}}"
                        ),
                        Sub(
                            f"arn:${{{AWS_PARTITION}}}:ssm:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}"
                            f":parameter${{{cw_config_parameter.title}}}"
                        ),
                    ],
                },
            ],
        },
    )
    return ecs_sd_policy


def add_cw_agent_to_family(family, **options):
    """
    Function to add the CW Agent to the task family for additional monitoring
    :param ecs_composex.common.compose_services.ComposeFamily family:
    """
    prometheus_config = set_cw_prometheus_config_parameter(family)
    cw_agent_config = set_cw_config_parameter(family, **options)
    family.add_service(
        define_cloudwatch_agent(family, prometheus_config, cw_agent_config)
    )
    family.refresh()
    task_role = family.template.resources[ecs_params.TASK_ROLE_T]
    exec_role = family.template.resources[ecs_params.EXEC_ROLE_T]
    ecs_sd_policy = set_ecs_cw_policy(prometheus_config, cw_agent_config)
    if hasattr(task_role, "Policies") and isinstance(
        getattr(task_role, "Policies"), list
    ):
        policies = getattr(task_role, "Policies")
        policies.append(ecs_sd_policy)
    elif not hasattr(task_role, "Policies"):
        setattr(task_role, "Policies", [ecs_sd_policy])
    if hasattr(exec_role, "Policies") and isinstance(
        getattr(exec_role, "Policies"), list
    ):
        policies = getattr(exec_role, "Policies")
        policies.append(ecs_sd_policy)
    elif not hasattr(exec_role, "Policies"):
        setattr(exec_role, "Policies", [ecs_sd_policy])
