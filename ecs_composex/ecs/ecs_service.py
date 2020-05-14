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
    Service as EcsService,
    PlacementStrategy,
    AwsvpcConfiguration,
    NetworkConfiguration,
    DeploymentController,
)

from ecs_composex.common import build_template, NONALPHANUM, KEYISSET, LOG
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.ecs import ecs_conditions
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_iam import add_service_roles
from ecs_composex.ecs.ecs_loadbalancing import define_grace_period
from ecs_composex.ecs.ecs_networking import (
    define_service_network_config,
    compile_network_settings,
)
from ecs_composex.ecs.ecs_task import add_task_defnition
from ecs_composex.vpc import vpc_params, vpc_conditions
from ecs_composex.common.config import ComposeXConfig

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
    EcsService(
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
            ecs_params.ECS_CONTROLLER,
            ecs_params.SERVICE_COUNT,
            ecs_params.CLUSTER_SG_ID,
            vpc_params.VPC_ID,
            vpc_params.APP_SUBNETS,
            vpc_params.PUBLIC_SUBNETS,
            vpc_params.VPC_MAP_ID,
            ecs_params.LOG_GROUP,
            ecs_params.SERVICE_HOSTNAME,
        ],
    )
    service_tpl.add_condition(
        ecs_conditions.MEM_RES_IS_MEM_ALLOC_CON_T,
        ecs_conditions.MEM_RES_IS_MEM_ALLOC_CON,
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
    service_tpl.add_condition(
        ecs_conditions.USE_HOSTNAME_CON_T, ecs_conditions.USE_HOSTNAME_CON
    )
    service_tpl.add_condition(
        ecs_conditions.NOT_USE_HOSTNAME_CON_T, ecs_conditions.NOT_USE_HOSTNAME_CON
    )
    return service_tpl


class ServiceConfig(ComposeXConfig):
    """
    Class specifically dealing with the configuration and settings of the service from how it was defined in
    the compose file
    """

    keys = ["image", "ports", "environment", "configs", "labels", "command", "hostname"]
    required_keys = ["image"]
    use_cloudmap = True
    use_nlb = None
    use_alb = None
    is_public = None
    healthcheck = None
    boundary = None
    lb_type = None
    hostname = None
    command = None

    def sort_load_balancing(self):
        """
        Function to sort out the load-balancing in case conflicting configuration
        :return:
        """
        self.lb_type = "application"
        if self.use_nlb and self.use_alb:
            LOG.warning(
                "Both ALB and NLB are enabled for this service. Defaulting to ALB"
            )
            self.use_nlb = False
        elif self.use_nlb and not self.use_alb:
            self.lb_type = "network"
        LOG.debug(f"Setting LB type to {self.lb_type}")

    def __init__(self, content, service_name, definition):
        """
        Function to initialize the service configuration
        :param content:
        """
        configs = {}
        if KEYISSET("configs", definition):
            configs = definition["configs"]
        super().__init__(content, service_name, configs)
        if not set(self.required_keys).issubset(set(definition)):
            raise AttributeError(
                "Required attributes for a service are", self.required_keys
            )
        self.image = definition["image"]
        self.sort_load_balancing()
        if KEYISSET("ports", definition):
            pass
        self.environment = (
            definition["environment"] if KEYISSET("environment", definition) else []
        )
        if KEYISSET("hostname", definition):
            self.hostname = definition["hostname"]


class Service(object):
    """
    Function to represent one service
    """

    links = []
    dependencies = []
    network_settings = None
    config = None

    def generate_service_template_outputs(self):
        """
        Function to generate the Service template outputs
        """
        self.template.add_output(
            formatted_outputs(
                [{ecs_params.SERVICE_GROUP_ID_T: GetAtt(ecs_params.SG_T, "GroupId")}],
                export=True,
                obj_name=self.resource_name,
            )
        )

    def __init__(self, service_name, definition, content, **kwargs):
        """
        Function to initialize the Service object
        :param service_name:
        :param service:
        """
        self.definition = definition
        print(service_name)
        self.config = ServiceConfig(content, service_name, definition)
        print(self.config)
        self.links = definition["links"] if KEYISSET("links", definition) else []
        self.dependencies = (
            definition["depends_on"] if KEYISSET("depends_on", definition) else []
        )
        self.service_name = service_name
        if not KEYISSET("image", definition):
            raise KeyError(f"No image property set for service {service_name}")
        self.environment = (
            definition["environment"] if KEYISSET("environment", definition) else []
        )
        self.resource_name = NONALPHANUM.sub("", self.service_name)
        self.hostname = (
            self.config.hostname if self.config.hostname else self.resource_name
        )

        self.network_settings = compile_network_settings(
            content, self.definition, self.service_name
        )
        self.template = initialize_service_template(self.resource_name)
        self.parameters = {
            vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
            vpc_params.VPC_MAP_ID_T: Ref(vpc_params.VPC_MAP_ID),
            vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
            ecs_params.CLUSTER_NAME_T: Ref(ecs_params.CLUSTER_NAME),
            ecs_params.LOG_GROUP.title: Ref(ecs_params.LOG_GROUP_T),
        }
        add_service_roles(self.template, self.config)
        add_task_defnition(self)

        self.sgs = [ecs_params.SG_T, ecs_params.CLUSTER_SG_ID]
        self.network_config = define_service_network_config(
            self.template, self.resource_name, self.network_settings, **kwargs
        )
        generate_service_definition(
            self.template, self.network_settings, self.sgs, **self.network_config[0]
        )
        self.generate_service_template_outputs()
