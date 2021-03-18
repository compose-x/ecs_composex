#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Core module for ECS ComposeX.

This module is going to parse each ecs_service and each x-resource key from the compose file
(hence ComposeX) and determine its

* ServiceDefinition
* TaskDefinition
* TaskRole
* ExecutionRole

It is going to also, based on the labels set in the compose file

* Add the ecs_service to Service Discovery via AWS CloudMap
* Add load-balancers to dispatch traffic to the microservice

"""

from ecs_composex import __version__ as version

metadata = {
    "Type": "ComposeX",
    "Properties": {"ecs_composex::module": "ecs_composex.ecs", "Version": version},
}
