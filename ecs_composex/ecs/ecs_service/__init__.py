# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Package to build the ECS Service Definition
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from troposphere import If, NoValue, Ref
from troposphere.ecs import DeploymentController, Service

from ecs_composex.ecs import ecs_conditions, ecs_params
from ecs_composex.ecs.ecs_conditions import use_external_lt_con
from ecs_composex.ecs.ecs_service.helpers import (
    define_deployment_options,
    define_placement_strategies,
)


class EcsService:
    """
    Class representing the service from the Docker compose file and translate it into
    AWS ECS Task Definition and Service.

    :ivar list links: the links used for DependsOn of the service stack
    :ivar list dependencies: list of services used for the DependsOn of the service stack
    :ivar ServiceConfig config: The service configuration
    :ivar troposphere.ecs.TaskDefinition task_definition: The service task definition for ECS
    :ivar list<troposphere.ec2.EIP> eips: list of AWS EC2 EIPs which are used for the public NLB
    :ivar dict service_attrs: Attributes defined to expand the troposphere.ecs.ServiceDefinition from prior settings.
    """

    def __init__(self, family: ComposeFamily):
        """
        Function to initialize the Service object

        :param ecs_composex.compose_services.ComposeFamily family:
        """
        self.family = family
        self.links = []
        self.service_attrs = {}
        self.dependencies = []
        self.ecs_service = None
        self.alarms = {}
        if family.stack:
            family.stack.Parameters.update({ecs_params.SERVICE_NAME_T: family.name})

        self.lbs = []
        self.registries = []
        self.service_tags = []

    def generate_service_definition(self, family: ComposeFamily) -> None:
        """
        Function to generate the Service definition.
        This is the last step in defining the service, after all other settings have been prepared.

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        from .helpers import set_service_default_tags_labels

        props = {}
        define_deployment_options(self.family, props)
        self.ecs_service = Service(
            ecs_params.SERVICE_T,
            template=self.family.template,
            TaskDefinition=Ref(self.family.task_definition),
            Cluster=Ref(ecs_params.CLUSTER_NAME),
            DeploymentController=DeploymentController(Type="ECS"),
            LaunchType=family.service_compute.cfn_launch_type,
            CapacityProviderStrategy=NoValue,
            EnableECSManagedTags=True,
            DesiredCount=If(
                ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
                1,
                If(
                    ecs_conditions.USE_FARGATE_CON_T,
                    Ref(ecs_params.SERVICE_COUNT),
                    If(
                        ecs_conditions.SERVICE_COUNT_ZERO_CON_T,
                        NoValue,
                        Ref(ecs_params.SERVICE_COUNT),
                    ),
                ),
            ),
            SchedulingStrategy=NoValue,
            PlacementStrategies=define_placement_strategies(),
            NetworkConfiguration=family.service_networking.ecs_network_config,
            LoadBalancers=use_external_lt_con(NoValue, self.lbs),
            ServiceRegistries=use_external_lt_con(NoValue, self.registries),
            Tags=set_service_default_tags_labels(self.family),
            PropagateTags="SERVICE",
            PlatformVersion=If(
                ecs_conditions.USE_FARGATE_CON_T,
                Ref(ecs_params.FARGATE_VERSION),
                NoValue,
            ),
            **props,
        )
