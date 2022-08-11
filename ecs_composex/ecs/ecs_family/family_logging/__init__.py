#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from troposphere.logs import LogGroup

from itertools import chain

from compose_x_common.compose_x_common import keyisset
from troposphere import Ref, Region, Sub

from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.logging import LOG
from ecs_composex.compose.compose_services.service_logging import ServiceLogging
from ecs_composex.ecs.ecs_firelens.firelens_advanced_rendered_settings import (
    handle_firelens_advanced_settings,
)
from ecs_composex.ecs.ecs_firelens.firelens_logger_helpers import (
    parse_set_update_firelens_configuration_options,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T, LOG_GROUP_RETENTION

from .cw_logging import (
    add_container_level_log_group,
    create_log_group,
    logging_from_defined_region,
)


class FamilyLogging:
    """
    :ivar LogGroup family_log_group:
    """

    def __init__(
        self,
        family: ComposeFamily,
    ):
        self._family = family
        self.logging_group_name = Sub(
            f"${{STACK_NAME}}/svc/ecs/${{{CLUSTER_NAME_T}}}/{family.logical_name}",
            STACK_NAME=define_stack_name(family.template if family.template else None),
        )
        self._family_log_group: LogGroup = create_log_group(
            self.family, group_name=self.logging_group_name, grant_task_role_access=True
        )
        self.firelens_service = None
        self.firelens_config_service = None
        self.services_logging: dict = {}
        self.firelens_advanced_config = None

    @property
    def family(self) -> ComposeFamily:
        return self._family

    @property
    def family_log_group(self) -> LogGroup:
        return self._family_log_group

    @property
    def cw_log_retention(self) -> int:
        return max(_svc.logging.cw_retention_period for _svc in self.family.services)

    def update_cw_log_retention(self):
        if self.family.stack:
            self.family.stack.Parameters.update(
                {LOG_GROUP_RETENTION.title: self.cw_log_retention}
            )

    @property
    def api_health_enabled(self):
        for _config in self.services_logging.values():
            if keyisset("EnableApiHeathCheck", _config.firelens_advanced):
                return True
        return False

    @property
    def buffer_limit_mb(self):
        """
        Returns the amount, in MB, of RAM to use for the log router (fluentbit) container
        """
        _mb = (2**10) ** 2
        _max = 512 * _mb
        default = 64
        defined = [
            _config.firelens_advanced["LogDriverBufferLimit"]
            for _config in self.services_logging.values()
            if keyisset("LogDriverBufferLimit", _config.firelens_advanced)
        ]
        if not defined:
            return default
        sum_defined = sum(defined)
        max_defined = max(defined)
        if max_defined < sum_defined < _max:
            return sum_defined / _mb
        elif sum_defined < max_defined < _max:
            return max_defined / _mb
        elif sum_defined > _max and max_defined > _max:
            return _max / _mb
        return default

    @property
    def grace_period(self):
        default = 30
        defined = [
            _config.firelens_advanced["GracePeriod"]
            for _config in self.services_logging.values()
            if keyisset("GracePeriod", _config.firelens_advanced)
        ]
        if not defined:
            return default
        max_defined = max(defined)
        if max_defined > 120:
            return 120
        elif max_defined < 0:
            return default
        else:
            return max_defined

    def init_family_services_log_configuration(self) -> None:
        for service in chain(
            self.family.managed_sidecars, self.family.ordered_services
        ):
            default_family_options = {
                "awslogs-group": Ref(self.family_log_group),
                "awslogs-region": Region,
                "awslogs-stream-prefix": service.name,
            }
            self.set_init_family_service_logging(service, default_family_options)
        self.update_cw_log_retention()

    def set_init_family_service_logging(self, service, awslogs_options):
        service.logging = ServiceLogging(service, awslogs_options)
        service.logging.set_update_log_configuration()
        setattr(
            service.container_definition,
            "LogConfiguration",
            service.logging.log_configuration,
        )
        self.services_logging[service] = service.logging

    def handle_firelens(self, settings):
        from ecs_composex.ecs.ecs_firelens.firelens_managed_sidecar_service import (
            FLUENT_BIT_AGENT_NAME,
            FluentBit,
            render_agent_config,
        )

        self.firelens_service = FluentBit(
            FLUENT_BIT_AGENT_NAME,
            render_agent_config(
                self.family, self.api_health_enabled, self.buffer_limit_mb
            ),
        )
        self.firelens_service.logging = ServiceLogging(
            self.firelens_service,
            {
                "awslogs-group": Ref(self.family_log_group),
                "awslogs-region": Region,
                "awslogs-stream-prefix": self.firelens_service.name,
            },
        )
        self.firelens_service.set_firelens_configuration()
        self.firelens_service.add_to_family(self.family, True)
        self.firelens_service.set_as_dependency_to_family_services()
        self.update_family_services_logging_configuration(settings)
        self.firelens_service.logging.set_update_log_configuration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Ref(self.family_log_group),
                "awslogs-region": Region,
                "awslogs-stream-prefix": self.firelens_service.name,
            },
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
            self.family.managed_sidecars, self.family.ordered_services
        ):
            if service is self.firelens_service:
                continue
            if service.is_aws_sidecar and not apply_to_sidecars:
                continue
            if service.logging.log_driver == "awsfirelens":
                LOG.debug(
                    f"{self.family.name}.{service.name} - LogDriver is already awsfirelens"
                )
                parse_set_update_firelens_configuration_options(
                    self.family, service, settings
                )
        self.firelens_advanced_config = handle_firelens_advanced_settings(
            self.family, settings
        )

    def handle_awslogs_logging(self, use_firelens: list):
        """
        Method to go over each service logging configuration and accordingly define the IAM permissions needed for
        the exec role

        If the region was passed in the log driver options, just grant access to any lo group
        ElIf the group name is set and is a string, passed by the log driver options, just grant access to it.
        """
        if not self.family.template:
            raise AttributeError(
                self.family.name,
                "Template not yet initialized. Must have a valid template to configure logging",
            )

        for service in chain(
            self.family.managed_sidecars, self.family.ordered_services
        ):
            if service in use_firelens:
                continue
            if keyisset("awslogs-region", service.logging.log_options) and isinstance(
                service.logging.log_options["awslogs-region"], str
            ):
                logging_from_defined_region(self.family, service)
            elif keyisset(
                "awslogs-group", service.logging.log_options
            ) and not isinstance(
                service.logging.log_options["awslogs-group"], (Ref, Sub)
            ):
                add_container_level_log_group(
                    self.family, service, f"{service.logical_name}LogGroupAccess"
                )
