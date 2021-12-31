#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for the ServiceConfig Class which is used for Container, Task and Service definitions.
"""

from compose_x_common.compose_x_common import keyisset

from ecs_composex.ecs.ecs_params import SERVICE_COUNT
from ecs_composex.ecs.ecs_scaling import ServiceScaling
from ecs_composex.ecs.ecs_service_network_config import ServiceNetworking


class ServiceConfig(object):
    """
    Class specifically dealing with the configuration and settings of the ecs_service from how it was defined in
    the compose file

    :ivar ServiceNetworking network: The network config for the service
    :ivar ecs_composex.ecs.ecs_scaling.ServiceScaling scaling: The scaling configuration for the service
    """

    def __init__(self, family, settings):
        """
        Function to initialize the ecs_service configuration

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.network = ServiceNetworking(family)
        self.scaling = ServiceScaling(family.ordered_services)
        self.use_appmesh = (
            False if not keyisset("x-appmesh", settings.compose_content) else True
        )
        self.replicas = max([service.replicas for service in family.services])
        if self.replicas != SERVICE_COUNT.Default:
            family.stack_parameters[SERVICE_COUNT.title] = self.replicas

    def debug(self):
        print(self.replicas, self.network, self.scaling)
