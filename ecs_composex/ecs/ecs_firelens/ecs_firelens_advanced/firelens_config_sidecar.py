#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_firelens.firelens_managed_sidecar_service import FluentBit

from compose_x_common.compose_x_common import keyisset

from ecs_composex.compose.compose_volumes import ComposeVolume
from ecs_composex.compose.compose_volumes.services_helpers import map_volumes
from ecs_composex.ecs.managed_sidecars import ManagedSidecar


def render_config_sidecar_config(
    family: ComposeFamily, volume_name: str, mount_path: str, ssm_parameter: str = None
):
    config: dict = {
        "image": "public.ecr.aws/compose-x/ecs-files-composer:latest",
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
        "volumes": [f"{volume_name}:{mount_path}"],
    }
    if ssm_parameter:
        config["command"] = [
            "--decode-base64",
            "--from-ssm",
            f"x-ssm_parameter::{ssm_parameter}::ParameterName",
        ]
    return config


def patch_fluent_service(
    fluent_service: FluentBit,
    shared_volume: ComposeVolume,
    sidecar_name: str,
    volume_name: str,
    mount_path: str,
) -> None:
    """

    :param FluentBit fluent_service:
    :param str sidecar_name:
    :param ComposeVolume shared_volume:
    :param str volume_name:
    :param str mount_path:
    :return:
    """
    if keyisset("volumes", fluent_service.definition):
        fluent_service.definition["volumes"].append(f"{volume_name}:{mount_path}")
    else:
        fluent_service.definition.update({"volumes": [f"{volume_name}:{mount_path}"]})
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
        shared_volume: ComposeVolume,
        mount_path: str,
    ):
        if keyisset(ComposeVolume.main_key, settings.compose_content):
            settings.compose_content[ComposeVolume.main_key][
                shared_volume.name
            ] = shared_volume
        else:
            settings.compose_content[ComposeVolume.main_key]: dict = {
                shared_volume.name: shared_volume
            }
        settings.volumes.append(shared_volume)

        super().__init__(name, definition, volumes=[shared_volume])
        patch_fluent_service(
            fluent_service, shared_volume, name, shared_volume.name, mount_path
        )
        fluent_service.depends_on.append(self.name)
