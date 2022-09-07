#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import AWSHelperFn, Ref, Region
from troposphere.ecs import Environment

from ecs_composex.compose.compose_services.helpers import extend_container_envvars
from ecs_composex.compose.compose_volumes.ecs_family_helpers import set_volumes

from .ecs_firelens_advanced import FireLensFamilyManagedConfiguration


def handle_firelens_advanced_settings(
    family: ComposeFamily, settings: ComposeXSettings
) -> FireLensFamilyManagedConfiguration:
    """
    Handles x-logging.FireLens.Advanced.Rendered

    :param ComposeFamily family:
    :param ComposeXSettings settings:
    """

    advanced_config = FireLensFamilyManagedConfiguration(family, settings)
    advanced_config.set_update_ssm_parameter(settings)
    env_vars = [
        Environment(Name=name, Value=str(value))
        for name, value in advanced_config.extra_env_vars.items()
        if isinstance(value, (int, float, str, bool))
    ]
    env_vars += [
        Environment(Name=name, Value=value)
        for name, value in advanced_config.extra_env_vars.items()
        if isinstance(value, AWSHelperFn) or issubclass(type(value), AWSHelperFn)
    ]
    extend_container_envvars(
        family.logging.firelens_service.container_definition, env_vars
    )
    extend_container_envvars(
        family.logging.firelens_config_service.container_definition, env_vars
    )
    family.logging.firelens_config_service.add_to_family(family, is_dependency=True)
    family.logging.firelens_config_service.logging.set_update_log_configuration(
        LogDriver="awslogs",
        Options={
            "awslogs-group": Ref(family.logging.family_log_group),
            "awslogs-region": Region,
            "awslogs-stream-prefix": family.logging.firelens_config_service.name,
        },
    )
    set_volumes(family)
    family.logging.firelens_service.firelens_config = {
        "Type": "fluentbit",
        "Options": {
            "config-file-value": f"{advanced_config.volume_mount}{advanced_config.config_file_name}",
            "config-file-type": "file",
            "enable-ecs-log-metadata": True,
        },
    }
    return advanced_config
