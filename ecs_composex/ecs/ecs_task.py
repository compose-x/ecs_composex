# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" ECS Task definition """

from troposphere import Ref, GetAtt, Tags, If
from troposphere.ecs import (
    PortMapping,
    Environment,
    LogConfiguration,
    ContainerDefinition,
    TaskDefinition,
)

from ecs_composex.common import add_parameters, KEYISSET
from ecs_composex.ecs import ecs_params, ecs_conditions
from ecs_composex.ecs.ecs_params import NETWORK_MODE, EXEC_ROLE_T, TASK_ROLE_T, TASK_T


def import_env_variables(service):
    """
    Function to import Docker compose env variables into ECS Env Variables
    :param service: service definition
    :type service: ecs_composex.ecs.ecs_service.Service

    :return: list of Environment
    :type: list<troposphere.ecs.Environment>
    """
    env_vars = []
    for key in service.environment:
        if not isinstance(service.environment[key], str):
            env_vars.append(Environment(Name=key, Value=str(service.environment[key])))
        else:
            env_vars.append(Environment(Name=key, Value=service.environment[key]))
    return env_vars


def generate_port_mappings(network_settings):
    """
    Generates a port mapping from the Docker compose file.
    Given we are going to use AWS VPC mode, we are only considering the app port.

    :returns: mappings, list of port mappings
    :rtype: list
    """
    mappings = []
    for port in network_settings["ports"]:
        mappings.append(
            PortMapping(ContainerPort=port["target"], HostPort=port["target"])
        )
    return mappings


def generate_container_definition(service, network_settings):
    """
    Generates the container definition
    """
    env_vars = import_env_variables(service)
    mappings = generate_port_mappings(network_settings)
    if not mappings:
        mappings = Ref("AWS::NoValue")
    container = ContainerDefinition(
        # EntryPoint=If(ENTRY_CON, Ref('AWS::NoValue'), Split(' ', Ref(params.SERVICE_ENTRYPOINT))),
        # Command=If(COMMAND_CON, Ref('AWS::NoValue'), Split('!!', Ref(params.SERVICE_COMMAND))),
        Image=Ref(ecs_params.SERVICE_IMAGE),
        Name=Ref(ecs_params.SERVICE_NAME),
        MemoryReservation=If(
            ecs_conditions.USE_FARGATE_CON_T,
            ecs_params.FARGATE_RAM,
            If(
                ecs_conditions.MEM_RES_IS_MEM_ALLOC_CON_T,
                Ref(ecs_params.MEMORY_ALLOC),
                Ref(ecs_params.MEMORY_RES),
            ),
        ),
        PortMappings=mappings,
        Environment=env_vars,
        LogConfiguration=LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Ref(ecs_params.CLUSTER_NAME),
                "awslogs-region": Ref("AWS::Region"),
                "awslogs-stream-prefix": Ref(ecs_params.LOG_GROUP),
            },
        ),
    )
    return container


def add_task_defnition(service):
    """
    Function to generate and add the task definition with container definitions
    to the service template

    :param service: the Service object
    :type service: ecs_composex.service.Service
    """
    add_parameters(
        service.template,
        [
            ecs_params.MEMORY_ALLOC,
            ecs_params.MEMORY_RES,
            ecs_params.SERVICE_NAME,
            ecs_params.SERVICE_IMAGE,
            ecs_params.FARGATE_CPU_RAM_CONFIG,
            ecs_params.TASK_CPU_COUNT,
        ],
    )
    service.template.add_condition(
        ecs_conditions.USE_FARGATE_CON_T, ecs_conditions.USE_FARGATE_CON
    )
    service.parameters.update(
        {
            ecs_params.SERVICE_IMAGE_T: service.image,
            ecs_params.SERVICE_NAME_T: service.service_name,
        }
    )
    TaskDefinition(
        TASK_T,
        template=service.template,
        Cpu=If(
            ecs_conditions.USE_FARGATE_CON_T,
            ecs_params.FARGATE_CPU,
            Ref(ecs_params.TASK_CPU_COUNT),
        ),
        Memory=If(
            ecs_conditions.USE_FARGATE_CON_T,
            ecs_params.FARGATE_RAM,
            Ref(ecs_params.MEMORY_ALLOC),
        ),
        NetworkMode=NETWORK_MODE,
        Family=Ref(ecs_params.SERVICE_NAME),
        TaskRoleArn=GetAtt(service.template.resources[TASK_ROLE_T], "Arn"),
        ExecutionRoleArn=GetAtt(service.template.resources[EXEC_ROLE_T], "Arn"),
        ContainerDefinitions=[
            generate_container_definition(service, service.network_settings)
        ],
        RequiresCompatibilities=["EC2", "FARGATE"],
        Tags=Tags(
            {"Name": Ref(ecs_params.SERVICE_NAME), "Environment": Ref("AWS::StackName")}
        ),
    )
