#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage the ``compute`` settings of the ECS Service

* Launch Type
* Capacity Providers

Unrelated to the Task compute settings (RAM/CPU)

"""
from troposphere import If, NoValue, Ref

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_conditions import USE_LAUNCH_TYPE_CON_T
from ecs_composex.ecs.ecs_params import LAUNCH_TYPE

from .helpers import merge_capacity_providers


class ServiceCompute(object):
    """
    Class to manage the ECS Service settings for launch type and capacity providers
    """

    def __init__(self, family):
        self.family = family
        self._launch_type = "EC2"
        self._ecs_capacity_providers = []

        self._cfn_launch_type = None
        self._cfn_capacity_providers = None
        self.set_update_launch_type()
        self.set_update_capacity_providers()

    @property
    def cfn_launch_type(self):
        return If(USE_LAUNCH_TYPE_CON_T, NoValue, Ref(LAUNCH_TYPE))

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
        self._ecs_capacity_providers = providers

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
        if self.launch_type == "EXTERNAL":
            LOG.debug(f"{self.family.name} is already set to EXTERNAL")
        for service in self.family.services:
            if service.launch_type == "EXTERNAL":
                LOG.info(
                    f"{self.family.name} - service {service.name} is set to EXTERNAL. Overriding for all"
                )
                self.launch_type = "EXTERNAL"
                break

    def set_compute_platform(self) -> None:
        """
        Iterates over all services and if ecs.compute.platform
        """
        if self.launch_type and self.launch_type == "EXTERNAL":
            return
        if self.launch_type != self.family.default_launch_type:
            LOG.debug(
                f"{self.family.name} - The compute platform is already overridden to {self.family.launch_type}"
            )
            for service in self.family.services:
                setattr(service, "compute_platform", self.family.launch_type)
        elif not all(
            service.launch_type == self.family.launch_type
            for service in self.family.services
        ):
            for service in self.family.services:
                if service.launch_type != self.launch_type:
                    platform = service.launch_type
                    LOG.debug(
                        f"{self.family.name} - At least one service is defined not to be on FARGATE."
                        f" Overriding to {platform}"
                    )
                    self.launch_type = platform
