#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings

from itertools import chain

from troposphere.ecs import FirelensConfiguration

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.managed_sidecars import ManagedSidecar

from .firelens_logger_helpers import parse_set_update_firelens_configuration_options

FLUENT_BIT_IMAGE_PARAMETER = Parameter(
    "FluentBitAwsImage",
    Type="AWS::SSM::Parameter::Value<String>",
    Default="/aws/service/aws-for-fluent-bit/latest",
)

FLUENT_BIT_AGENT_NAME = "log_router"


def render_agent_config(family: ComposeFamily) -> dict:
    return {
        "image": "public.ecr.aws/aws-observability/aws-for-fluent-bit:latest",
        "deploy": {
            "resources": {
                "limits": {"cpus": 0.1, "memory": "64M"},
                "reservations": {"memory": "32M"},
            },
        },
        "expose": ["24224/tcp"],
        "labels": {"container_name": "log_router"},
        "logging": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": family.family_logging_prefix,
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


class FluentBit(ManagedSidecar):
    fluentbit_firelens_defaults: dict = {
        "Type": "fluentbit",
        "Options": {"enable-ecs-log-metadata": True},
    }

    def __init__(self, name, definition):
        super().__init__(
            name, definition, is_essential=True, image_param=FLUENT_BIT_IMAGE_PARAMETER
        )

    def set_firelens_configuration(self):
        setattr(
            self.container_definition,
            "FirelensConfiguration",
            FirelensConfiguration(**self.fluentbit_firelens_defaults),
        )

    def add_to_family(self, family: ComposeFamily, is_dependency: bool = False) -> None:
        """
        Adds the container as a sidecar to the family in order to fulfil a specific purpose
        for an AWS Feature, here, add xray-daemon for dynamic tracing.

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        :param bool is_dependency: Whether the family services depend on sidecar or not.
        """
        self.my_family = family
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
            self.my_family.managed_sidecars, self.my_family.ordered_services
        ):
            if service is self:
                continue
            print("SERVICE?", service.name, service.depends_on)
            if self.name not in service.depends_on:
                service.depends_on.append(self.name)
                LOG.info(
                    f"{self.my_family.name}.{service.name} - Added {self.name} as startup dependency"
                )

    def update_family_services_logging_configuration(
        self,
        settings: ComposeXSettings,
        apply_to_sidecars: bool = False,
    ):
        """
        Updates all the container definitions of the ComposeFamily services
        """
        for service in chain(
            self.my_family.managed_sidecars, self.my_family.ordered_services
        ):
            if service is self:
                continue
            if service.is_aws_sidecar and not apply_to_sidecars:
                continue
            container_definition = getattr(service, "container_definition")
            logging_config = getattr(container_definition, "LogConfiguration")
            if logging_config.LogDriver == "awsfirelens":
                LOG.info(
                    f"{self.my_family.name}.{service.name} - LogDriver is already awsfirelens"
                )
                LOG.info(logging_config.Options)
                parse_set_update_firelens_configuration_options(
                    self.my_family, service, logging_config, settings
                )
                continue
            else:
                setattr(logging_config, "LogDriver", "awsfirelens")
