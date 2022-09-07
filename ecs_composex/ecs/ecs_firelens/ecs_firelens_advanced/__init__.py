#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Handles ``Rendered`` section of the FireLens configuration
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily

import copy
from os import environ, path

from compose_x_common.compose_x_common import keyisset, set_else_none
from jinja2 import Environment, FileSystemLoader
from troposphere import Ref, Region

from ecs_composex.common.logging import LOG
from ecs_composex.compose.compose_services.service_logging import ServiceLogging
from ecs_composex.compose.compose_volumes import ComposeVolume

from .advanced_firehose import FireLensFirehoseManagedDestination
from .advanced_kinesis import FireLensKinesisManagedDestination
from .config_parameter import add_managed_ssm_parameter
from .firelens_config_sidecar import FluentBitConfig, render_config_sidecar_config


class FireLensFamilyManagedConfiguration:
    volume_mount: str = "/compose_x_rendered/"
    volume_name: str = "compose-x-firelens-rendering"
    config_file_name: str = "firelens.conf"

    def __init__(self, family: ComposeFamily, settings: ComposeXSettings):
        self._config_volume = ComposeVolume(self.volume_name, {})
        self._family = family
        _services_with_advanced = []
        for _svc in family.services:
            if _svc.logging and _svc.logging.firelens_advanced:
                _services_with_advanced.append((_svc, _svc.logging.firelens_advanced))
        self._ssm_parameter = None
        self._parser_files: dict = {}
        self.family.logging.firelens_config_service = FluentBitConfig(
            "log_router_preload",
            render_config_sidecar_config(
                family, self.volume_name, self.volume_mount, self.ssm_parameter_title
            ),
            family.logging.firelens_service,
            settings,
            shared_volume=self.config_volume,
            mount_path=self.volume_mount,
        )
        self.family.logging.firelens_config_service.logging = ServiceLogging(
            self.family.logging.firelens_config_service,
            {
                "awslogs-group": Ref(self.family.logging.family_log_group),
                "awslogs-region": Region,
                "awslogs-stream-prefix": self.family.logging.firelens_config_service.name,
            },
        )

        self.services_configs: dict = {}
        for service, definition in _services_with_advanced:
            self.services_configs[service] = FireLensServiceManagedConfiguration(
                service, definition, family, settings
            )

    @property
    def family(self) -> ComposeFamily:
        return self._family

    @property
    def ssm_parameter_title(self) -> str:
        return f"{self.family.logical_name}FireLensConfigurationSsm"

    @property
    def config_volume(self) -> ComposeVolume:
        return self._config_volume

    @property
    def extra_env_vars(self) -> dict:
        _env_vars = {}
        for config in self.services_configs.values():
            for key, value in config.extra_env_vars.items():
                if key not in _env_vars:
                    _env_vars[key] = value
        return _env_vars

    def set_update_ssm_parameter(self, settings):
        """
        Sets ssm parameter or updates content
        """
        content: dict = {
            "files": {
                f"{self.volume_mount}{self.config_file_name}": {
                    "content": self.rendered_content
                }
            }
        }
        content["files"].update(self.parser_files)
        if not self._ssm_parameter:
            self._ssm_parameter = add_managed_ssm_parameter(
                self.family, settings, content
            )

    @property
    def parser_files(self) -> dict:
        self._parser_files = {}
        for _svc in self.services_configs.values():
            for _parser_file, _parser_file_def in _svc.parser_files.items():
                if not keyisset("content", _parser_file_def):
                    continue
                file_path = f"{self.volume_mount}{_parser_file}"
                if file_path not in self._parser_files.keys():
                    self._parser_files[
                        f"{self.volume_mount}{_parser_file}"
                    ] = _parser_file_def
        return self._parser_files

    @property
    def parser_files_names(self) -> list:
        files_names: list = []
        for _svc in self.services_configs.values():
            for _parser_file, _parser_file_def in _svc.parser_files.items():
                if keyisset("content", _parser_file_def):
                    file_path = f"{self.volume_mount}{_parser_file}"
                    self._parser_files.update({file_path: _parser_file_def})
                else:
                    file_path = _parser_file
                if file_path not in files_names:
                    files_names.append(file_path)
        return files_names

    @property
    def rendered_content(self):
        here = path.abspath(path.dirname(__file__))
        jinja_env = Environment(
            loader=FileSystemLoader(here),
            autoescape=True,
            auto_reload=False,
        )
        template = jinja_env.get_template("family_fluentbit_managed_config.j2")
        content = template.render(
            env=environ,
            enable_health_check=self.family.logging.api_health_enabled,
            grace_period=self.family.logging.grace_period,
            services_content=[
                _svc.render_jinja_config_file()
                for _svc in self.services_configs.values()
            ],
            parser_files=self.parser_files_names,
        )
        return content


class FireLensServiceManagedConfiguration:
    def __init__(self, service, definition: dict, family, settings: ComposeXSettings):
        self.service = service
        self._definition = copy.deepcopy(definition)
        self.family = family
        self.source_file = set_else_none("SourceFile", self.definition)
        self._parser_files = set_else_none("ParserFiles", self.definition, alt_value=[])
        self._env_vars = set_else_none("EnvironmentVariables", self.definition)
        self.managed_destinations = []
        self.extra_env_vars = set_else_none(
            "EnvironmentVariables", self.definition, alt_value={}
        )

        if keyisset("ComposeXManagedAwsDestinations", self.definition):
            for destination_definition in self.definition[
                "ComposeXManagedAwsDestinations"
            ]:
                if keyisset("log_group_name", destination_definition):
                    self.managed_destinations.append(
                        FireLensCloudWatchManagedDestination(
                            destination_definition, self, settings
                        )
                    )
                elif keyisset("delivery_stream", destination_definition):
                    self.managed_destinations.append(
                        FireLensFirehoseManagedDestination(
                            destination_definition, self, settings
                        )
                    )
                elif keyisset("stream", destination_definition):
                    self.managed_destinations.append(
                        FireLensKinesisManagedDestination(
                            destination_definition, self, settings
                        )
                    )
                else:
                    LOG.error("Invalid definition for ComposeXManagedAwsDestinations")
                    LOG.error(destination_definition)

    @property
    def definition(self):
        return self._definition

    @property
    def managed_firehose_destinations(self):
        managed_firehose: list = []
        for _managed_dest in self.managed_destinations:
            if isinstance(_managed_dest, FireLensFirehoseManagedDestination):
                managed_firehose.append(_managed_dest)
        return managed_firehose

    @property
    def managed_data_streams_destinations(self):
        managed_data_stream: list = []
        for _managed_dest in self.managed_destinations:
            if isinstance(_managed_dest, FireLensKinesisManagedDestination):
                managed_data_stream.append(_managed_dest)
        return managed_data_stream

    @property
    def parser_files(self) -> dict:
        files: dict = {}
        for _file in self._parser_files:
            file_name = path.basename(_file)
            try:
                with open(_file) as file_fd:
                    content = file_fd.read()
                files[file_name]: dict = {"content": content}
            except OSError:
                LOG.warning(
                    f"{self.family.name} - FireLens Advanced - {_file} not found."
                    " Assuming it already is in the image"
                )
                files[_file]: dict = {}
        return files

    @property
    def source_file_content(self) -> str:
        if not self.source_file:
            return ""
        with open(path.abspath(self.source_file)) as config_fd:
            return config_fd.read()

    def render_jinja_config_file(self):
        here = path.abspath(path.dirname(__file__))
        jinja_env = Environment(
            loader=FileSystemLoader(here),
            autoescape=True,
            auto_reload=False,
        )
        template = jinja_env.get_template("service_fluentbit_managed_config.j2")
        content = template.render(
            env=environ,
            firelens_firehose_destinations=self.managed_firehose_destinations,
            firelens_data_streams_destinations=self.managed_data_streams_destinations,
            source_file=self.source_file_content,
            service_match=f"{self.service.name}-firelens*",
        )
        LOG.debug(content)
        return content


class FireLensCloudWatchManagedDestination:
    def __init__(
        self,
        definition: dict,
        advanced_config: FireLensServiceManagedConfiguration,
        settings: ComposeXSettings,
    ):
        self._definition = definition
        self.output_definition = None
        self.parent = advanced_config

    @property
    def log_group_name(self) -> str:
        return self._definition["log_group_name"]
