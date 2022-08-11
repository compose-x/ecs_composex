#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from itertools import chain

from compose_x_common.compose_x_common import keyisset
from troposphere import If, NoValue, Ref, Sub
from troposphere.ecs import FirelensConfiguration

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters
from ecs_composex.ecs.ecs_conditions import USE_FARGATE_CON_T
from ecs_composex.ecs.managed_sidecars import ManagedSidecar

FLUENT_BIT_IMAGE_PARAMETER = Parameter(
    "FluentBitAwsImage",
    Type="AWS::SSM::Parameter::Value<String>",
    Default="/aws/service/aws-for-fluent-bit/latest",
)

FLUENT_BIT_AGENT_NAME = "log_router"
DEFAULT_LIMIT = 64


def render_agent_config(
    family: ComposeFamily,
    api_health_enabled: bool = False,
    enable_prometheus: bool = False,
    memory_limits: int = DEFAULT_LIMIT,
) -> dict:
    if memory_limits > 512:
        LOG.error(
            f"{family.name} - FireLens container memory exceeds 512MB. Setting to 512MB"
        )
        memory_limits = 512
    elif memory_limits < DEFAULT_LIMIT:
        memory_limits = DEFAULT_LIMIT
    config: dict = {
        "image": "public.ecr.aws/aws-observability/aws-for-firehose_destination.bit:latest",
        "deploy": {
            "resources": {
                "limits": {"cpus": 0.1, "memory": f"{memory_limits}M"},
                "reservations": {"memory": "32M"},
            },
        },
        "labels": {"container_name": "log_router"},
        "logging": {
            "driver": "awslogs",
            "options": {
                "awslogs-group": Ref(family.logging.family_log_group),
                "awslogs-stream-prefix": "firelens",
                "awslogs-create-group": True,
            },
        },
        "healthcheck": {
            "test": [
                "CMD-SHELL",
                'echo \'{"health": "check"}\' | nc 127.0.0.1 8877 || exit 1',
            ],
            "interval": "10s",
            "retries": 3,
            "start_period": "5s",
            "timeout": "2s",
        },
    }
    if api_health_enabled:
        config.update(
            {
                "healthcheck": {
                    "test": [
                        "CMD-SHELL",
                        "curl -sq http://127.0.0.1:2020/api/v1/health  || exit 1",
                    ],
                    "interval": "10s",
                    "retries": 3,
                    "start_period": "5s",
                    "timeout": "2s",
                }
            }
        )
    if enable_prometheus:
        config["ports"] = [{"target": 2021, "protocol": "tcp"}]
    return config


class FluentBit(ManagedSidecar):
    fluentbit_firelens_defaults: dict = {
        "Type": "fluentbit",
        "Options": {"enable-ecs-log-metadata": True},
    }

    def __init__(self, name, definition):
        super().__init__(
            name, definition, is_essential=True, image_param=FLUENT_BIT_IMAGE_PARAMETER
        )

    @property
    def firelens_config(self):
        return (
            getattr(self.container_definition, "FirelensConfiguration")
            if hasattr(self.container_definition, "FirelensConfiguration")
            else NoValue
        )

    @firelens_config.setter
    def firelens_config(self, config):
        if keyisset("config-file-type", config) and config["config-file-type"] == "s3":
            config["config-file-type"] = If(
                USE_FARGATE_CON_T, NoValue, config["config-file-type"]
            )
            config["config-file-value"] = If(
                USE_FARGATE_CON_T, NoValue, config["config-file-value"]
            )
            parts = re.match(
                r"arn:aws(-[a-z-]+)?:s3:::(?P<bucket>[a-zA-Z-.\d][^/]+)/(?P<path>[\S]+)$",
                config["config-file-value"],
            )
            if parts and parts.group("bucket"):
                from ecs_composex.resource_settings import define_iam_permissions

                define_iam_permissions(
                    "s3",
                    self.family,
                    self.family.template,
                    "s3ForFirelens",
                    {
                        "RO": {
                            "Action": ["s3:GetObject*", "s3:ListBucket"],
                            "Effect": "Allow",
                        }
                    },
                    access_definition="RO",
                    resource_arns=[
                        Sub(f"arn:aws:s3:::{parts.group('bucket')}"),
                        Sub(f"arn:aws:s3:::{parts.group('bucket')}/*"),
                    ],
                    roles=[
                        self.family.iam_manager.task_role.name,
                        self.family.iam_manager.exec_role.name,
                    ],
                )
        setattr(
            self.container_definition,
            "FirelensConfiguration",
            FirelensConfiguration(**config),
        )

    def set_firelens_configuration(self):
        self.firelens_config = self.fluentbit_firelens_defaults

    def add_to_family(self, family: ComposeFamily, is_dependency: bool = False) -> None:
        """
        Adds the container as a sidecar to the family in order to fulfil a specific purpose
        for an AWS Feature, here, add xray-daemon for dynamic tracing.

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        :param bool is_dependency: Whether the family services depend on sidecar or not.
        """
        self.family = family
        family.add_managed_sidecar(self)
        add_parameters(family.template, [FLUENT_BIT_IMAGE_PARAMETER])
        self.image_param = FLUENT_BIT_IMAGE_PARAMETER
        self.set_as_dependency_to_family_services(is_dependency)

    def set_as_dependency_to_family_services(self, is_dependency: bool = True) -> None:
        """
        As it is the logging router, it needs to start before every other container
        :param is_dependency:
        :return:
        """
        for service in chain(
            self.family.managed_sidecars, self.family.ordered_services
        ):
            if service is self:
                continue
            if self.name not in service.depends_on:
                service.depends_on.append(self.name)
                LOG.info(
                    f"{self.family.name}.{service.name} - Added {self.name} as startup dependency"
                )
