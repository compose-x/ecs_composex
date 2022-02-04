#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to build the ECS Service Definition
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, GetAtt, If, Join, Ref
from troposphere.ecs import AwsvpcConfiguration
from troposphere.ecs import DeploymentCircuitBreaker as EcsDeploymentCircuitBreaker
from troposphere.ecs import (
    DeploymentConfiguration,
    DeploymentController,
    NetworkConfiguration,
    PlacementStrategy,
)
from troposphere.ecs import Service as EcsService

from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.ecs import ecs_conditions, ecs_params
from ecs_composex.ecs.ecs_conditions import use_external_lt_con
from ecs_composex.vpc import vpc_params

from .ecs_scaling import ServiceScaling
from .ecs_service_network_config import ServiceNetworking


def define_placement_strategies():
    """
    Function to generate placement strategies. Defaults to spreading across all AZs

    :return: list of placement strategies
    :rtype: list
    """
    return [
        PlacementStrategy(Field="instanceId", Type="spread"),
        PlacementStrategy(Field="attribute:ecs.availability-zone", Type="spread"),
    ]


def generate_service_template_outputs(family):
    """
    Function to generate the Service template outputs
    """
    family.template.add_output(
        ComposeXOutput(
            family.logical_name,
            [
                (
                    ecs_params.SERVICE_GROUP_ID_T,
                    "GroupId",
                    GetAtt(family.service_config.network.security_group, "GroupId"),
                ),
                (
                    ecs_params.TASK_T,
                    ecs_params.TASK_T,
                    Ref(family.task_definition),
                ),
                (
                    vpc_params.APP_SUBNETS,
                    vpc_params.APP_SUBNETS.title,
                    Join(",", Ref(vpc_params.APP_SUBNETS)),
                ),
                (
                    family.scalable_target.title,
                    ecs_params.SERVICE_SCALING_TARGET,
                    Ref(family.scalable_target),
                ),
            ],
            duplicate_attr=False,
            export=False,
        ).outputs
    )


def define_deployment_options(family, settings, kwargs):
    """
    Function to define the DeploymentConfiguration

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param dict kwargs:
    :return:
    """
    family.set_service_update_config()
    default = DeploymentConfiguration(
        DeploymentCircuitBreaker=EcsDeploymentCircuitBreaker(
            Enable=True, Rollback=True
        ),
    )
    if family.deployment_config:
        deploy_config = DeploymentConfiguration(
            MaximumPercent=int(family.deployment_config["MaximumPercent"]),
            MinimumHealthyPercent=int(
                family.deployment_config["MinimumHealthyPercent"]
            ),
            DeploymentCircuitBreaker=EcsDeploymentCircuitBreaker(
                Enable=True,
                Rollback=keyisset("RollBack", family.deployment_config),
            ),
        )
        kwargs.update({"DeploymentConfiguration": deploy_config})
    else:
        kwargs.update({"DeploymentConfiguration": default})


class Service(object):
    """
    Class representing the service from the Docker compose file and translate it into
    AWS ECS Task Definition and Service.

    :ivar list links: the links used for DependsOn of the service stack
    :ivar list dependencies: list of services used for the DependsOn of the service stack
    :ivar ServiceConfig config: The service configuration
    :ivar troposphere.ecs.TaskDefinition task_definition: The service task definition for ECS
    :ivar list<troposphere.ec2.EIP> eips: list of AWS EC2 EIPs which are used for the public NLB
    :ivar dict service_attrs: Attributes defined to expand the troposphere.ecs.ServiceDefinition from prior settings.
    :ivar ServiceNetwork network:
    :ivar replicas:
    :ivar ServiceScaling scaling:
    """

    def __init__(self, family, settings):
        """
        Function to initialize the Service object

        :param ecs_composex.compose_services.ComposeFamily family:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.links = []
        self.service_attrs = {}
        self.dependencies = []
        self.ecs_service = None
        self.scalable_target = None
        self.scaling_out_policies = {}
        self.scaling_in_policies = {}
        self.alarms = {}
        family.stack_parameters.update({ecs_params.SERVICE_NAME_T: family.name})

        self.network = ServiceNetworking(family)
        self.scaling = ServiceScaling(family.ordered_services)
        self.use_appmesh = (
            False if not keyisset("x-appmesh", settings.compose_content) else True
        )
        self.replicas = max([service.replicas for service in family.services])
        if self.replicas != ecs_params.SERVICE_COUNT.Default:
            family.stack_parameters[ecs_params.SERVICE_COUNT.title] = self.replicas

        self.lbs = []
        self.registries = []
        self.security_groups = []
        self.subnets = []

    def generate_service_definition(self, family, settings):
        """
        Function to generate the Service definition.
        This is the last step in defining the service, after all other settings have been prepared.

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        props = {}
        define_deployment_options(family, settings, props)
        self.ecs_service = EcsService(
            ecs_params.SERVICE_T,
            template=family.template,
            Cluster=Ref(ecs_params.CLUSTER_NAME),
            DeploymentController=DeploymentController(
                Type=Ref(ecs_params.ECS_CONTROLLER)
            ),
            CapacityProviderStrategy=Ref(AWS_NO_VALUE),
            EnableECSManagedTags=True,
            DesiredCount=If(
                ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
                1,
                If(
                    ecs_conditions.USE_FARGATE_CON_T,
                    Ref(ecs_params.SERVICE_COUNT),
                    If(
                        ecs_conditions.SERVICE_COUNT_ZERO_CON_T,
                        Ref(AWS_NO_VALUE),
                        Ref(ecs_params.SERVICE_COUNT),
                    ),
                ),
            ),
            SchedulingStrategy=Ref(AWS_NO_VALUE),
            PlacementStrategies=Ref(AWS_NO_VALUE),
            NetworkConfiguration=use_external_lt_con(
                Ref(AWS_NO_VALUE),
                NetworkConfiguration(
                    AwsvpcConfiguration=AwsvpcConfiguration(
                        Subnets=self.subnets,
                        SecurityGroups=self.security_groups,
                    )
                ),
            ),
            TaskDefinition=Ref(family.task_definition),
            LaunchType=If(
                ecs_conditions.USE_LAUNCH_TYPE_CON_T,
                Ref(ecs_params.LAUNCH_TYPE),
                Ref(AWS_NO_VALUE),
            ),
            Tags=family.service_tags,
            PropagateTags="SERVICE",
            PlatformVersion=If(
                ecs_conditions.USE_FARGATE_CON_T,
                Ref(ecs_params.FARGATE_VERSION),
                Ref(AWS_NO_VALUE),
            ),
            LoadBalancers=use_external_lt_con(Ref(AWS_NO_VALUE), self.lbs),
            ServiceRegistries=use_external_lt_con(Ref(AWS_NO_VALUE), self.registries),
            **props,
        )
