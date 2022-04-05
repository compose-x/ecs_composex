# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Core module for ECS ComposeX.

This module is going to parse each ecs_service and each x-resource key from the compose file
(hence Compose-X) and determine its

* ServiceDefinition
* TaskDefinition
* TaskRole
* ExecutionRole

It is going to also, based on the labels set in the compose file

* Add the ecs_service to Service Discovery via AWS CloudMap
* Add load-balancers to dispatch traffic to the microservice

Services logic

* Define Container Definitions
** Compute
** Storage
** Docker Settings
** Logging Settings
** Env Vars
** Secrets

* Define Task Definition
** IAM Roles
** Containers
** Volumes (Docker volumes / EFS)
** AppMesh/Proxy Settings

* Define Service Definition
** Network settings (VPC/SG)
** Ingress settings (ALB/NLB/CloudMap)


"""

from ecs_composex import __version__ as version

metadata = {
    "Type": "ComposeX",
    "Properties": {
        "ecs_composex::module": "ecs_composex.ecs",
        "Version": version,
    },
}
