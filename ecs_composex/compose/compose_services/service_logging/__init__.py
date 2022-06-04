#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from . import ComposeService
    from ecs_composex.ecs.ecs_family import ComposeFamily

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import NoValue
from troposphere.ecs import LogConfiguration

from ecs_composex.compose.compose_services.service_logging.helpers import (
    get_closest_valid_log_retention_period,
    handle_awslogs_options,
    handle_firelens_options,
    replace_awslogs_with_firelens_configuration,
)
from ecs_composex.ecs.ecs_params import LOG_GROUP_RETENTION


class ServiceLogging:
    """
    Class to handle a single service / container definition logging settings
    """

    def __init__(self, service: ComposeService, default_options: dict):
        self._service = service
        self._log_configuration = NoValue
        self.def_logging = set_else_none("logging", service.definition)
        self.def_x_logging = set_else_none("x-logging", service.definition)
        self._log_driver = None
        self._log_options: dict = {}
        self.log_driver = set_else_none("driver", self.def_logging, alt_value="awslogs")
        self.log_options = set_else_none(
            "options", self.def_logging, alt_value=default_options
        )
        self.cw_retention_period = get_closest_valid_log_retention_period(
            set_else_none(
                "RetentionInDays",
                self.def_x_logging,
                alt_value=LOG_GROUP_RETENTION.Default,
            )
        )

    @property
    def uses_firelens(self) -> bool:
        if (
            self.firelens_shorthands
            or self.firelens_advanced
            or self.log_driver == "awsfirelens"
        ):
            return True
        return False

    @property
    def log_config(self):
        return {"driver": self.log_driver, "options": self.log_options}

    @property
    def log_driver(self) -> str:
        if self.log_configuration and isinstance(
            self.log_configuration, LogConfiguration
        ):
            return self.log_configuration.LogDriver
        else:
            return self._log_driver

    @log_driver.setter
    def log_driver(self, driver: str) -> None:
        self._log_driver = driver
        if self.log_configuration and isinstance(
            self.log_configuration, LogConfiguration
        ):
            self.log_configuration.LogDriver = self._log_driver

    @property
    def log_options(self) -> dict:
        if self.log_configuration and isinstance(
            self.log_configuration, LogConfiguration
        ):
            return self.log_configuration.Options
        else:
            return self._log_options

    @log_options.setter
    def log_options(self, options: dict) -> None:
        self._log_options.update(options)
        if self.log_configuration and isinstance(
            self.log_configuration, LogConfiguration
        ):
            self.log_configuration.Options = self._log_options

    @property
    def service(self) -> ComposeService:
        return self._service

    @property
    def family(self) -> Union[ComposeFamily, None]:
        if self.service.family:
            return self.service.family
        return None

    @property
    def firelens_config(self) -> dict:
        return set_else_none("FireLens", self.def_x_logging, alt_value={})

    @property
    def firelens_shorthands(self) -> dict:
        return set_else_none("Shorthands", self.firelens_config)

    @property
    def firelens_advanced(self) -> dict:
        return set_else_none("Advanced", self.firelens_config)

    @property
    def replace_cw_with_firelens(self) -> bool:
        if self.firelens_shorthands and keyisset(
            "ReplaceAwsLogs", self.firelens_shorthands
        ):
            return True
        return False

    @property
    def log_configuration(self) -> Union[LogConfiguration, None]:
        return self._log_configuration

    @log_configuration.setter
    def log_configuration(self, config: LogConfiguration) -> None:
        self._log_configuration = config
        setattr(
            self.service.container_definition,
            "LogConfiguration",
            self._log_configuration,
        )

    def set_update_log_configuration(self, **kwargs):
        if kwargs and keyisset("LogDriver", kwargs) and keyisset("Options", kwargs):
            self.log_configuration = LogConfiguration(**kwargs)
            return
        if self.log_driver == "awslogs":
            self.log_configuration = handle_awslogs_options(
                self.service, self.log_config
            )
            if self.replace_cw_with_firelens:
                self.log_configuration = replace_awslogs_with_firelens_configuration(
                    self.service, self.log_configuration
                )
        elif self.log_driver == "awsfirelens":
            self.log_configuration = handle_firelens_options(
                self.service, self.log_config
            )
