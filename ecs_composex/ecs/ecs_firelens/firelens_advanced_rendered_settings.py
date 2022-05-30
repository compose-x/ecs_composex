#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from json import dumps
from os import path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import Ref, Region
from troposphere.ecs import LogConfiguration
from troposphere.ssm import Parameter as CfnSsmParameter

from ecs_composex.common import LOG, add_resource
from ecs_composex.compose.compose_volumes.ecs_family_helpers import set_volumes
from ecs_composex.resources_import import import_record_properties
from ecs_composex.ssm_parameter.ssm_parameter_stack import SsmParameter

from .ecs_firelens_managed import FireLensManagedConfiguration
from .firelens_cloudwatch_helpers import (
    handle_cloudwatch_log_group_name,
    set_default_cloudwatch_logging_options,
)
from .firelens_firehose_helpers import handle_x_kinesis_firehose
from .firelens_managed_config_sidecar import (
    FluentBitConfig,
    render_config_sidecar_config,
)
from .firelens_options_generic_helpers import handle_cross_account_permissions


def add_managed_ssm_parameter(
    family: ComposeFamily,
    settings: ComposeXSettings,
    rendered_settings: FireLensManagedConfiguration,
) -> str:
    """
    Handles x-logging.FireLens.Advanced.Rendered

    :param family:
    :param settings:
    :param rendered_settings:
    """

    render_config = {
        "files": {
            "/rendered/firelens.conf": {
                "content": rendered_settings.render_jinja_config_file()
            }
        }
    }
    ssm_parameter_title = f"{family.logical_name}FireLensConfigurationSsm"
    ssm_parameter_definition = {
        "Properties": {
            "DataType": "text",
            "Type": "String",
            "Value": dumps(render_config),
        },
        "MacroParameters": {"EncodeToBase64": True},
        "Services": {family.name: {"Access": "RO"}},
    }

    if "x-ssm_parameter" not in settings.mod_manager.modules:
        ssm_module = settings.mod_manager.add_module("x-ssm_parameter")
        settings.compose_content[ssm_module.res_key]: dict = {
            ssm_parameter_title: ssm_parameter_definition
        }
    else:
        ssm_module = settings.mod_manager.modules["x-ssm_parameter"]
        settings.compose_content[ssm_module.res_key].update(
            {ssm_parameter_title: ssm_parameter_definition}
        )
    if not ssm_module:
        raise LookupError("Failed to import x-ssm_parameter module!")

    if ssm_module.mod_key not in settings.stacks:
        ssm_stack = ssm_module.stack_class(ssm_module.mod_key, settings, ssm_module)
        settings.stacks[ssm_module.mod_key] = ssm_stack
        add_resource(settings.root_stack.stack_template, ssm_stack)
    else:
        ssm_parameter = SsmParameter(
            ssm_parameter_title, ssm_parameter_definition, ssm_module, settings
        )
        ssm_parameter.stack = settings.stacks[ssm_module.mod_key]
        ssm_parameter.init_outputs()
        ssm_parameter.generate_outputs()
        add_resource(ssm_parameter.stack.stack_template, ssm_parameter.cfn_resource)
        ssm_parameter.to_ecs(settings, settings.mod_manager)

    return ssm_parameter_title


def handle_rendered_settings(
    family: ComposeFamily, settings: ComposeXSettings, rendered_settings: dict
) -> None:
    """
    Handles x-logging.FireLens.Advanced.Rendered

    :param family:
    :param settings:
    :param rendered_settings:
    """

    from troposphere.ecs import Environment

    from ecs_composex.compose.compose_services.helpers import extend_container_envvars

    advanced_config = FireLensManagedConfiguration(rendered_settings)
    advanced_config.render_jinja_config_file()

    ssm_parameter = add_managed_ssm_parameter(family, settings, advanced_config)
    extra_env_vars = set_else_none(
        "EnvironmentVariables", rendered_settings, alt_value={}
    )
    family.firelens_config_service = FluentBitConfig(
        "log_router_preload",
        render_config_sidecar_config(family, ssm_parameter, extra_env_vars),
        family.firelens_service,
        settings,
    )
    env_vars = [
        Environment(Name=name, Value=value) for name, value in extra_env_vars.items()
    ]
    extend_container_envvars(family.firelens_service.container_definition, env_vars)
    family.firelens_config_service.add_to_family(family, is_dependency=True)
    setattr(
        family.firelens_config_service.container_definition,
        "LogConfiguration",
        LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Ref(family.umbrella_log_group),
                "awslogs-region": Region,
                "awslogs-stream-prefix": family.firelens_config_service.name,
            },
        ),
    )
    set_volumes(family)
    family.firelens_service.firelens_config = {
        "Type": "fluentbit",
        "Options": {
            "config-file-value": "/rendered/firelens.conf",
            "config-file-type": "file",
            "enable-ecs-log-metadata": True,
        },
    }
