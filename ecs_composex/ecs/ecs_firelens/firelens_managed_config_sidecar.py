#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings
    from .firelens_managed_sidecar_service import FluentBit

from compose_x_common.compose_x_common import keyisset
from troposphere import Ref

from ecs_composex.compose.compose_volumes import ComposeVolume
from ecs_composex.compose.compose_volumes.services_helpers import map_volumes
from ecs_composex.ecs.managed_sidecars import ManagedSidecar


def render_config_sidecar_config(
    family: ComposeFamily, ssm_parameter: str = None, environment: dict = None
):
    config: dict = {
        "image": "public.ecr.aws/compose-x/ecs-files-composer:d1a1abb",
        "deploy": {
            "resources": {
                "limits": {"cpus": 0.1, "memory": "64M"},
                "reservations": {"memory": "32M"},
            },
            "labels": {
                "ecs.task.family": family.name,
                "ecs.depends.condition": "SUCCESS",
            },
        },
        "labels": {"container_name": "log_router_configuration"},
        "logging": {
            "driver": "awslogs",
            "options": {
                "awslogs-group": Ref(family.umbrella_log_group)
                if family.umbrella_log_group
                else family.family_logging_prefix,
                "awslogs-stream-prefix": "firelens_config",
                "awslogs-create-group": True,
            },
        },
        "volumes": ["fluent-rendering:/rendered/"],
    }
    if ssm_parameter:
        config["command"] = [
            "--decode-base64",
            "--from-ssm",
            f"x-ssm_parameter::{ssm_parameter}::ParameterName",
        ]
    if environment:
        config["environment"] = environment
    return config


def patch_fluent_service(
    fluent_service: FluentBit, shared_volume: ComposeVolume, sidecar_name: str
) -> None:
    """

    :param FluentBit fluent_service:
    :param str sidecar_name:
    :param ComposeVolume shared_volume:
    :return:
    """
    if keyisset("volumes", fluent_service.definition):
        fluent_service.definition["volumes"].append("fluent-rendering:/rendered/")
    else:
        fluent_service.definition.update({"volumes": ["fluent-rendering:/rendered/"]})
    map_volumes(fluent_service, [shared_volume])

    if keyisset("depends_on", fluent_service.definition):
        fluent_service.definition["depends_on"].append(sidecar_name)
    else:
        fluent_service.definition.update({"depends_on": [sidecar_name]})


class FluentBitConfig(ManagedSidecar):
    """
    Sidecar to pull/render the configuration file to use for fluentbit / fluentd
    """

    def __init__(
        self,
        name,
        definition,
        fluent_service: FluentBit,
        settings: ComposeXSettings,
        volumes: list = None,
    ):
        if volumes is None:
            volumes = []
        shared_volume = ComposeVolume("fluent-rendering", {})
        volumes.append(shared_volume)
        if keyisset(ComposeVolume.main_key, settings.compose_content):
            settings.compose_content[ComposeVolume.main_key][
                "fluent-rendering"
            ] = shared_volume
        else:
            settings.compose_content[ComposeVolume.main_key]: dict = {
                "fluent-rendering": shared_volume
            }
        settings.volumes.append(shared_volume)

        super().__init__(name, definition, volumes=volumes)
        patch_fluent_service(fluent_service, shared_volume, name)
        fluent_service.depends_on.append(self.name)
