#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage the ``compute`` settings of the ECS Service

* Launch Type
* Capacity Providers

Unrelated to the Task compute settings (RAM/CPU)

"""
from troposphere import If, NoValue, Ref

from ecs_composex.common.logging import LOG
from ecs_composex.ecs.ecs_conditions import (
    DISABLE_CAPACITY_PROVIDERS_CON_T,
    USE_LAUNCH_TYPE_CON_T,
)
from ecs_composex.ecs.ecs_params import LAUNCH_TYPE

from .helpers import merge_capacity_providers


class ServiceCompute:
    """
    Class to manage the ECS Service settings for launch type and capacity providers
    """

    def __init__(self, family):
        self.family = family
        self._launch_type = None
        self._ecs_capacity_providers = []

        self._cfn_launch_type = None
        self._cfn_capacity_providers = None
        self.set_update_launch_type()
        self.set_update_capacity_providers()

    @property
    def cfn_launch_type(self):
        return If(USE_LAUNCH_TYPE_CON_T, Ref(LAUNCH_TYPE), NoValue)

    @property
    def launch_type(self):
        return self._launch_type

    @launch_type.setter
    def launch_type(self, launch_type):
        self._launch_type = launch_type
        if self.family.stack:
            self.family.stack.Parameters.update({LAUNCH_TYPE.title: self._launch_type})

    @property
    def ecs_capacity_providers(self):
        return self._ecs_capacity_providers

    @ecs_capacity_providers.setter
    def ecs_capacity_providers(self, providers):
        if not isinstance(providers, list):
            raise TypeError(
                "ECS Capacity Providers must be a list. Got", providers, type(providers)
            )
        self._ecs_capacity_providers = providers
        if self.family.ecs_service and self.family.ecs_service.ecs_service:
            setattr(
                self.family.ecs_service.ecs_service,
                "CapacityProviderStrategy",
                If(
                    DISABLE_CAPACITY_PROVIDERS_CON_T,
                    NoValue,
                    providers,
                ),
            )

    def set_update_capacity_providers(self) -> None:
        """
        If the Launch Type is not EXTERNAL, will merge the capacity providers defined by the services.x-ecs
        of the family services.
        """
        if self.launch_type and self.launch_type != "EXTERNAL":
            merge_capacity_providers(self)

    def set_update_launch_type(self) -> None:
        """
        Goes over all the services and verifies if one of them is set to use EXTERNAL mode.
        If so, overrides for all
        """
        launch_modes = [
            _svc.launch_type
            for _svc in self.family.ordered_services
            if _svc.launch_type
        ]
        modes_priority_ordered = ["EXTERNAL", "EC2", "FARGATE"]
        for mode in modes_priority_ordered:
            if mode in launch_modes and self.launch_type != mode:
                LOG.info(
                    f"{self.family.name} - At least one service defined for EXTERNAL. Overriding for all"
                )
                self.launch_type = mode
                break
        else:
            LOG.debug(
                f"{self.family.name} - Using default Launch Type - {LAUNCH_TYPE.Default}"
            )
