#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from troposphere import (
    Parameter,
    AWS_NO_VALUE,
)
from troposphere import Ref
from troposphere.ecs import (
    LogConfiguration,
    ContainerDefinition,
    HealthCheck,
    ContainerDependency,
    PortMapping,
)

from ecs_composex.common import add_parameters
from ecs_composex.common import keyisset
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_container_config import import_env_variables


class Container(object):
    """
    Class to represent the container definition and its settings
    """

    parameters = {}
    required_keys = ["image"]

    def __init__(self, template, title, definition, config):
        """

        :param troposphere.Template template: template to add the container definition to
        :param str title: name of the resource / service
        :param dict definition: service definition
        :param ServiceConfig config: service configuration
        """
        if not set(self.required_keys).issubset(set(definition)):
            raise AttributeError(
                "Required attributes for a ecs_service are", self.required_keys
            )
        image_param = Parameter(
            f"{title}ImageUrl",
            Type="String",
            Description=f"ImageURL for {title}",
        )
        add_parameters(template, [image_param])
        self.stack_parameters = {image_param.title: definition["image"]}
        if isinstance(config.cpu_alloc, int):
            cpu_config = config.cpu_alloc
        elif isinstance(config.cpu_alloc, Ref) and isinstance(config.cpu_resa, int):
            cpu_config = config.cpu_resa
        else:
            cpu_config = Ref(AWS_NO_VALUE)
        self.definition = ContainerDefinition(
            f"{title}Container",
            Image=Ref(image_param),
            Name=title,
            Cpu=cpu_config,
            Memory=config.mem_alloc,
            MemoryReservation=config.mem_resa,
            PortMappings=[
                PortMapping(ContainerPort=port, HostPort=port)
                for port in config.ingress_mappings.keys()
            ]
            if keyisset("ports", definition)
            else Ref(AWS_NO_VALUE),
            Environment=import_env_variables(definition["environment"])
            if keyisset("environment", definition)
            else Ref(AWS_NO_VALUE),
            LogConfiguration=LogConfiguration(
                LogDriver="awslogs",
                Options={
                    "awslogs-group": Ref(ecs_params.LOG_GROUP_T),
                    "awslogs-region": Ref("AWS::Region"),
                    "awslogs-stream-prefix": title,
                },
            ),
            Command=definition["command"].strip().split(";")
            if keyisset("command", definition)
            else Ref(AWS_NO_VALUE),
            DependsOn=[ContainerDependency(**args) for args in config.family_dependents]
            if config.family_dependents
            else Ref(AWS_NO_VALUE),
            Essential=config.essential,
            HealthCheck=config.healthcheck
            if isinstance(config.healthcheck, HealthCheck)
            else Ref(AWS_NO_VALUE),
        )
        values = []
        if isinstance(config.cpu_resa, int):
            values.append(("Cpu", "Cpu", str(config.cpu_resa)))
        if isinstance(config.cpu_resa, int):
            values.append(("Memory", "Memory", str(config.mem_alloc)))
        if isinstance(config.mem_resa, int):
            values.append(
                ("MemoryReservation", "MemoryReservation", str(config.mem_resa))
            )
        template.add_output(ComposeXOutput(title, values, export=False).outputs)
