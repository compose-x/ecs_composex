#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage the ``compute`` settings of the ECS Service

* Launch Type
* Capacity Providers

Unrelated to the Task compute settings (RAM/CPU)

"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

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
        self.family: ComposeFamily = family
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
            self.apply_capacity_providers_to_service(providers)

    def apply_capacity_providers_to_service(self, providers: list):
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
        Defines all the possible launch types defined on the services of the task into `launch_types`
        If this is the first time we run the function, and we don't have either self.launch_type nor `launch_types`
        we default to Fargate
        Considering that `EXTERNAL` > `EC2` > `FARGATE` in priority, we stop at that launch_type as soon as any service
        has it set in its properties.
        If launch_type wasn't set, we stop at the highest priority type
        If launch_type was already set, we evaluate it a new service might have a different launch_type, higher priority
        If we are already all set, debug log it.
        Otherwise, if somehow we didn't get into any of these conditions, pick default => Fargate
        """
        launch_types = [
            _svc.launch_type
            for _svc in self.family.ordered_services
            if _svc.launch_type
        ]
        if not self.launch_type and not launch_types:
            LOG.info(
                "services.{} - No Launch Type defined. Using default: {}".format(
                    self.family.name, LAUNCH_TYPE.Default
                )
            )
            self.launch_type = LAUNCH_TYPE.Default
            return

        launch_types_priority_ordered = ["EXTERNAL", "EC2", "FARGATE"]
        for _launch_type in launch_types_priority_ordered:
            type_in_family_launch_types: bool = _launch_type in launch_types
            type_is_defined_launch_type: bool = self.launch_type == _launch_type

            if not self.launch_type and type_in_family_launch_types:
                LOG.info(
                    f"{self.family.name} - Init LaunchType {_launch_type}, requested by at least one service."
                )
                self.launch_type = _launch_type
                break
            elif (
                self.launch_type
                and type_in_family_launch_types
                and not type_is_defined_launch_type
            ):
                LOG.info(
                    f"{self.family.name} - A service in family requires {_launch_type} instead of {self.launch_type}."
                    " Overriding."
                )
                self.launch_type = _launch_type
                break
            elif (
                self.launch_type
                and type_in_family_launch_types
                and type_is_defined_launch_type
            ):
                LOG.debug(f"{self.family.name} is already set to {_launch_type}")
                break
        else:
            LOG.debug(
                "{} - Using default Launch Type - {}".format(
                    self.family.name, LAUNCH_TYPE.Default
                )
            )
            self.launch_type = LAUNCH_TYPE.Default
