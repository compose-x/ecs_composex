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

"""
Functions to build the ECS Service Definition
"""

from troposphere import Tags, GetAtt, Ref, If, Join
from troposphere.ecs import (
    Service,
    PlacementStrategy,
    AwsvpcConfiguration,
    NetworkConfiguration,
    DeploymentController,
)

from ecs_composex.common import build_template, cfn_params, add_parameters
from ecs_composex.common import cfn_conditions
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.common.tagging import add_object_tags
from ecs_composex.ecs import ecs_conditions
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_iam import add_service_roles
from ecs_composex.ecs.ecs_loadbalancing import define_grace_period
from ecs_composex.ecs.ecs_networking import (
    define_service_network_config,
    compile_network_settings,
)
from ecs_composex.ecs.ecs_networking_ingress import define_service_to_service_ingress
from ecs_composex.ecs.ecs_task import add_task_defnition
from ecs_composex.vpc import vpc_params, vpc_conditions

STATIC = 0


def define_placement_strategies():
    """
    Function to generate placement strategies
    :return: list of placement strategies
    :rtype: list
    """
    return [
        PlacementStrategy(Field="instanceId", Type="spread"),
        PlacementStrategy(Field="attribute:ecs.availability-zone", Type="spread"),
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
                    Ref("AWS::NoValue"),
                    Ref(ecs_params.SERVICE_COUNT),
                ),
            ),
        ),
        SchedulingStrategy=If(
            ecs_conditions.USE_FARGATE_CON_T,
            "REPLICA",
            If(
                ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T, "REPLICA", "DAEMON"
            ),
        ),
        HealthCheckGracePeriodSeconds=define_grace_period(template, network_settings),
        PlacementStrategies=If(
            ecs_conditions.USE_FARGATE_CON_T,
            Ref("AWS::NoValue"),
            define_placement_strategies(),
        ),
        NetworkConfiguration=NetworkConfiguration(
            AwsvpcConfiguration=AwsvpcConfiguration(
                Subnets=Ref(vpc_params.APP_SUBNETS), SecurityGroups=service_sgs
            )
        ),
        TaskDefinition=Ref(ecs_params.TASK_T),
        LaunchType=Ref(ecs_params.LAUNCH_TYPE),
        Tags=Tags(
            {"Name": Ref(ecs_params.SERVICE_NAME), "StackName": Ref("AWS::StackName")}
        ),
        PropagateTags="SERVICE",
        **kwargs,
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
            vpc_params.VPC_MAP_ID,
            ecs_params.LOG_GROUP,
        ],
    )
    service_tpl.add_condition(
        ecs_conditions.MEM_RES_IS_MEM_ALLOC_CON_T,
        ecs_conditions.MEM_RES_IS_MEM_ALLOC_CON,
    )
    service_tpl.add_condition(
        cfn_conditions.USE_CLOUDMAP_CON_T, cfn_conditions.USE_CLOUDMAP_CON
    )
    service_tpl.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_CON_T, ecs_conditions.SERVICE_COUNT_ZERO_CON
    )
    service_tpl.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON,
    )
    service_tpl.add_condition(
        vpc_conditions.USE_VPC_MAP_ID_CON_T, vpc_conditions.USE_VPC_MAP_ID_CON
    )
    service_tpl.add_condition(
        vpc_conditions.NOT_USE_VPC_MAP_ID_CON_T, vpc_conditions.NOT_USE_VPC_MAP_ID_CON
    )
    return service_tpl


def generate_service_template_outputs(template, service_name):
    """
    Function to generate the Service template outputs

    :param template: service template
    :type template: troposphere.Template
    :param service_name: name of the service as defined in Docker ComposeX file
    """
    template.add_output(
        formatted_outputs(
            [{ecs_params.SERVICE_GROUP_ID_T: GetAtt(ecs_params.SG_T, "GroupId")}],
            export=True,
            obj_name=service_name,
        )
    )


def generate_service_template(
    compose_content, service_name, service, tags=None, session=None, **kwargs,
):
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
    network_settings = compile_network_settings(compose_content, service, service_name)
    service_tpl = initialize_service_template(service_name)
    parameters = {
        vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
        vpc_params.VPC_MAP_ID_T: Ref(vpc_params.VPC_MAP_ID),
        vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
        vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
        ecs_params.CLUSTER_NAME_T: Ref(ecs_params.CLUSTER_NAME),
        ecs_params.LOG_GROUP.title: Ref(ecs_params.LOG_GROUP_T),
    }
    if tags and tags[0]:
        add_parameters(service_tpl, tags[0])
        for tag in tags[0]:
            parameters.update({tag.title: Ref(tag.title)})
    add_service_roles(service_tpl)
    parameters.update(
        add_task_defnition(service_tpl, service_name, service, network_settings)
    )
    service_sgs = [ecs_params.SG_T, ecs_params.CLUSTER_SG_ID]
    service_network_config = define_service_network_config(
        service_tpl, service_name, network_settings, **kwargs
    )
    generate_service_definition(
        service_tpl, network_settings, service_sgs, **service_network_config[0]
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
    if tags and tags[1]:
        for resource in service_tpl.resources:
            add_object_tags(service_tpl.resources[resource], tags[1])
    return service_tpl, parameters, stack_dependencies
