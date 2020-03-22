# -*- coding: utf-8 -*-
"""
Functions to build the ECS Service Definition
"""

from troposphere import (
    Tags, GetAtt,
    Ref, If, Join
)
from troposphere.ecs import (
    Service,
    PlacementStrategy,
    AwsvpcConfiguration,
    NetworkConfiguration,
    DeploymentController
)

from ecs_composex.common import LOG, cfn_conditions
from ecs_composex.common import (
    build_template, cfn_params
)
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T
)
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.common.templates import upload_template
from ecs_composex.ecs import ecs_conditions
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_iam import (
    add_service_roles,
    assign_x_resources_to_service
)
from ecs_composex.ecs.ecs_loadbalancing import define_grace_period
from ecs_composex.ecs.ecs_networking import (
    define_service_network_config,
    compile_network_settings
)
from ecs_composex.ecs.ecs_networking_ingress import define_service_to_service_ingress
from ecs_composex.ecs.ecs_task import (
    add_task_defnition
)
from ecs_composex.vpc import vpc_params

STATIC = 0


def define_placement_strategies():
    """
    Function to generate placement strategies
    :return: list of placement strategies
    :rtype: list
    """
    return [
        PlacementStrategy(
            Field='instanceId',
            Type='spread'
        ),
        PlacementStrategy(
            Field='attribute:ecs.availability-zone',
            Type='spread'
        )
    ]


def generate_service_definition(template, network_settings, security_groups, **kwargs):
    """Function to generate the Service definition

    :param template: service template
    :type template: troposphere.Template
    :param network_settings: network settings as defined in compile_network_settings
    :type network_settings: dict
    :param security_groups: list of security groups for the service to use
    :type security_groups: list
    :param kwargs: extra settings that the Service() object can add to
    :type kwargs: dict
    """

    service_sgs = [Ref(sg) for sg in security_groups]
    Service(
        ecs_params.SERVICE_T,
        template=template,
        Cluster=Ref(ecs_params.CLUSTER_NAME),
        DeploymentController=DeploymentController(Type=Ref(ecs_params.ECS_CONTROLLER)),
        EnableECSManagedTags=True,
        DesiredCount=If(
            ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
            1,
            If(
                ecs_conditions.USE_FARGATE_CON_T,
                Ref(ecs_params.SERVICE_COUNT),
                If(
                    ecs_conditions.SERVICE_COUNT_ZERO_CON_T,
                    Ref('AWS::NoValue'),
                    Ref(ecs_params.SERVICE_COUNT)
                )
            )
        ),
        SchedulingStrategy=If(
            ecs_conditions.USE_FARGATE_CON_T,
            'REPLICA',
            If(
                ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
                'REPLICA',
                'DAEMON'
            )
        ),
        HealthCheckGracePeriodSeconds=define_grace_period(template, network_settings),
        PlacementStrategies=If(
            ecs_conditions.USE_FARGATE_CON_T,
            Ref('AWS::NoValue'),
            define_placement_strategies()
        ),
        NetworkConfiguration=NetworkConfiguration(
            AwsvpcConfiguration=AwsvpcConfiguration(
                Subnets=Ref(vpc_params.APP_SUBNETS),
                SecurityGroups=service_sgs
            )
        ),
        TaskDefinition=Ref(ecs_params.TASK_T),
        LaunchType=Ref(ecs_params.LAUNCH_TYPE),
        Tags=Tags(
            {
                'Name': Ref(ecs_params.SERVICE_NAME),
                'StackName': Ref('AWS::StackName')
            }
        ),
        PropagateTags='SERVICE',
        **kwargs
    )


def initialize_service_template(service_name):
    """Function to initialize the base template for ECS Services with all
    parameters and conditions necessary for CFN to work properly

    :param service_name: Name of the service as defined in ComposeX File
    :type service_name: str

    :return: service_template
    :rtype: troposphere.Template
    """
    service_tpl = build_template(
        f"Template for {service_name}",
        [
            ecs_params.CLUSTER_NAME,
            ecs_params.LAUNCH_TYPE,
            cfn_params.SERVICE_DISCOVERY,
            ecs_params.ECS_CONTROLLER,
            ecs_params.SERVICE_COUNT,
            ecs_params.CLUSTER_SG_ID,
            vpc_params.VPC_ID,
            vpc_params.APP_SUBNETS,
            vpc_params.PUBLIC_SUBNETS,
            ecs_params.LOG_GROUP
        ]
    )
    service_tpl.add_condition(
        ecs_conditions.MEM_RES_IS_MEM_ALLOC_CON_T,
        ecs_conditions.MEM_RES_IS_MEM_ALLOC_CON
    )
    service_tpl.add_condition(
        cfn_conditions.USE_CLOUDMAP_CON_T,
        cfn_conditions.USE_CLOUDMAP_CON
    )
    service_tpl.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_CON_T,
        ecs_conditions.SERVICE_COUNT_ZERO_CON
    )
    service_tpl.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON
    )
    return service_tpl


def generate_service_template_outputs(template, service_name):
    """
    Function to generate the Service template outputs

    :param template: service template
    :type template: troposphere.Template
    :param service_name: name of the service as defined in Docker ComposeX file
    """
    template.add_output(formatted_outputs([
        {
            ecs_params.SERVICE_GROUP_ID_T: GetAtt(ecs_params.SG_T, 'GroupId')
        }
    ], export=True, prefix=f"${{{ROOT_STACK_NAME_T}}}-{service_name}"))


def generate_service_template(compose_content, service_name, service, session=None, **kwargs):
    """
    Function to generate single service template based on its definition in
    the Compose file.

    :param compose_content: Docker/ComposeX Content
    :type compose_content: dict
    :param service_name: Name of the service as defined in ComposeX
    :type service_name: str
    :param service: service dict as defined in ComposeX
    :type service: dict
    :param session: boto3 session for override
    :type session: boto3.session.Session

    :returns: service template URL, service specific parameters, stack dependencies
    :rtype: tuple
    """
    network_settings = compile_network_settings(
        compose_content, service, service_name
    )
    service_tpl = initialize_service_template(service_name)
    parameters = {
        vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
        vpc_params.APP_SUBNETS_T: Join(',', Ref(vpc_params.APP_SUBNETS)),
        vpc_params.PUBLIC_SUBNETS_T: Join(',', Ref(vpc_params.PUBLIC_SUBNETS)),
        ecs_params.CLUSTER_NAME_T: Ref(ecs_params.CLUSTER_NAME),
        ecs_params.LOG_GROUP.title: Ref(ecs_params.LOG_GROUP_T)
    }
    add_service_roles(service_tpl)
    parameters.update(add_task_defnition(
        service_tpl, service_name, service, network_settings
    ))
    assign_x_resources_to_service(
        compose_content, service_name,
        service_tpl, **kwargs
    )
    service_sgs = [ecs_params.SG_T, ecs_params.CLUSTER_SG_ID]
    service_network_config = define_service_network_config(
        service_tpl, service_name, network_settings, **kwargs
    )
    generate_service_definition(
        service_tpl, network_settings, service_sgs,
        **service_network_config[0]
    )
    services_dependencies = define_service_to_service_ingress(
        compose_content, service_tpl, service_name, service
    )
    stack_dependencies = []
    if isinstance(service_network_config[-1], list):
        stack_dependencies += service_network_config[-1]
    if isinstance(services_dependencies, list):
        stack_dependencies += services_dependencies
    generate_service_template_outputs(service_tpl, service_name)
    service_tpl_url = upload_template(
        service_tpl.to_json(),
        kwargs['BucketName'],
        f"{service_name}.json",
        session=session
    )
    LOG.debug(service_tpl_url)
    return service_tpl_url, parameters, stack_dependencies
