# -*- coding: utf-8 -*-
""" ECS Task definition """

from troposphere import (
    Ref, GetAtt, Tags, If
)
from troposphere.ecs import (
    PortMapping, Environment,
    LogConfiguration,
    ContainerDefinition,
    TaskDefinition
)

from ecs_composex.common import (
    add_parameters,
    KEYISSET
)
from ecs_composex.ecs.ecs_params import (
    NETWORK_MODE,
    EXEC_ROLE_T,
    TASK_ROLE_T,
    TASK_T
)
from ecs_composex.ecs import ecs_params, ecs_conditions


def import_env_variables(service):
    """
    Function to import Docker compose env variables into ECS Env Variables
    :param service: service definition
    :type service: dict

    :return: list of Environment
    :type: list<troposphere.ecs.Environment>
    """
    env_vars = []
    if KEYISSET('environment', service):
        for key in service['environment']:
            env_vars.append(
                Environment(
                    Name=key,
                    Value=service['environment'][key]
                )
            )
    return env_vars


def generate_port_mappings(network_settings):
    """
    Generates a port mapping from the Docker compose file.
    Given we are going to use AWS VPC mode, we are only considering the app port.

    :returns: mappings, list of port mappings
    :rtype: list
    """
    mappings = []
    for port in network_settings['ports']:
        mappings.append(PortMapping(
            ContainerPort=port['target'],
            HostPort=port['target']
        ))
    return mappings


def generate_container_definition(service, network_settings):
    """
    Generates the container definition
    """
    mappings = Ref('AWS::NoValue')
    env_vars = import_env_variables(service)
    mappings = generate_port_mappings(network_settings)
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
                Ref(ecs_params.MEMORY_RES)
            )
        ),
        PortMappings=mappings,
        Environment=env_vars,
        LogConfiguration=LogConfiguration(
            LogDriver='awslogs',
            Options={
                'awslogs-group': Ref(ecs_params.CLUSTER_NAME),
                'awslogs-region': Ref('AWS::Region'),
                'awslogs-stream-prefix': Ref(ecs_params.LOG_GROUP)
            }
        )
    )
    return container


def add_task_defnition(template, service_name, service, network_settings):
    """
    Function to generate and add the task definition with container definitions
    to the service template

    :param network_settings: network settings as defined in compile_network_settings
    :type network_settings: dict
    :param template: The service template to add definitions to
    :type template: troposphere.Template
    :param service_name: Name of the service
    :type service_name: str
    :param service: the service dict object
    :type service: dict
    """
    add_parameters(
        template,
        [
            ecs_params.MEMORY_ALLOC,
            ecs_params.MEMORY_RES,
            ecs_params.SERVICE_NAME,
            ecs_params.SERVICE_IMAGE,
            ecs_params.FARGATE_CPU_RAM_CONFIG,
            ecs_params.TASK_CPU_COUNT
        ]
    )
    template.add_condition(
        ecs_conditions.USE_FARGATE_CON_T,
        ecs_conditions.USE_FARGATE_CON
    )
    parameters = {
        ecs_params.SERVICE_IMAGE_T: service['image'],
        ecs_params.SERVICE_NAME_T: service_name
    }
    TaskDefinition(
        TASK_T,
        template=template,
        Cpu=If(
            ecs_conditions.USE_FARGATE_CON_T,
            ecs_params.FARGATE_CPU,
            Ref(ecs_params.TASK_CPU_COUNT)
        ),
        Memory=If(
            ecs_conditions.USE_FARGATE_CON_T,
            ecs_params.FARGATE_RAM,
            Ref(ecs_params.MEMORY_ALLOC),
        ),
        NetworkMode=NETWORK_MODE,
        Family=Ref(ecs_params.SERVICE_NAME),
        TaskRoleArn=GetAtt(template.resources[TASK_ROLE_T], 'Arn'),
        ExecutionRoleArn=GetAtt(template.resources[EXEC_ROLE_T], 'Arn'),
        ContainerDefinitions=[
            generate_container_definition(service, network_settings)
        ],
        RequiresCompatibilities=[
            'EC2',
            'FARGATE'
        ],
        Tags=Tags(
            {
                'Name': Ref(ecs_params.SERVICE_NAME),
                'Environment': Ref('AWS::StackName')
            }
        )
    )
    return parameters
