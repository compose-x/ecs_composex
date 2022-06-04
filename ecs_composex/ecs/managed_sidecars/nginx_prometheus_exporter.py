#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Simple class to manage AWS XRay sidecar
"""

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.managed_sidecars import ManagedSidecar

NGINX_EXPORTER_IMAGE_PARAMETER = Parameter(
    "NginxPrometheusExporterImage",
    Type="String",
    Default="public.ecr.aws/nginx/nginx-prometheus-exporter:latest",
)

NGINX_EXPORTER_NAME = "cloudwatch-agent"
NGINX_EXPORTER_DEFINITION = {
    "image": NGINX_EXPORTER_IMAGE_PARAMETER.Default,
    "deploy": {
        "resources": {"limits": {"cpus": 0.1, "memory": "64M"}},
    },
    "labels": {
        "container_name": "nginx-prometheus-exporter",
        "ECS_PROMETHEUS_EXPORTER_PORT": 9113,
        "job": "nginx-prometheus-exporter",
    },
    "ports": [{"target": 9113, "protocol": "tcp"}],
}

NGINX_EXPORTER_SERVICE = ManagedSidecar(
    NGINX_EXPORTER_NAME,
    NGINX_EXPORTER_DEFINITION,
)
