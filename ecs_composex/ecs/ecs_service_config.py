#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module for the ServiceConfig Class which is used for Container, Task and Service definitions.
"""

from ecs_composex.common import keyisset
from ecs_composex.ecs.ecs_params import SERVICE_COUNT
from ecs_composex.ecs.ecs_scaling import ServiceScaling
from ecs_composex.ecs.ecs_service_network_config import ServiceNetworking


class ServiceConfig(object):
    """
    Class specifically dealing with the configuration and settings of the ecs_service from how it was defined in
    the compose file

    :cvar list keys: List of valid settings for a service in Docker compose syntax reference
    :cvar list service_config_keys: list of extra configuration that apply to services.
    :cvar bool UseCloudmap: Indicates whether or not the service will be added to the VPC CloudMap
    :cvar bool use_alb: Indicates to use an AWS Application LoadBalancer (ELBv2, type application)
    :cvar bool use_nlb: Indicates to use an AWS Application LoadBalancer (ELBv2, type network)
    :cvar bool is_public: Indicates whether the service should be accessible publicly
    """

    def __init__(self, family, settings):
        """
        Function to initialize the ecs_service configuration

        :param ecs_composex.common.compose_services.ComposeFamily family:
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
