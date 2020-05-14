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

from troposphere import Join
from troposphere import Ref, GetAtt, Tags, If
from troposphere.ecs import (
    PortMapping,
    Environment,
    LogConfiguration,
    ContainerDefinition,
    TaskDefinition,
)
from troposphere.ecs import (
    Service as EcsService,
    PlacementStrategy,
    AwsvpcConfiguration,
    NetworkConfiguration,
    DeploymentController,
)

from ecs_composex.common import add_parameters
from ecs_composex.common import build_template, NONALPHANUM, KEYISSET, LOG
from ecs_composex.common.config import ComposeXConfig
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.ecs import ecs_params, ecs_conditions
from ecs_composex.ecs.ecs_iam import add_service_roles
from ecs_composex.ecs.ecs_loadbalancing import define_grace_period
from ecs_composex.ecs.ecs_networking import (
    define_service_network_config,
    compile_network_settings,
    define_protocol,
    add_service_to_map,
    add_service_default_sg,
    define_service_load_balancing,
)
from ecs_composex.ecs.ecs_params import NETWORK_MODE, EXEC_ROLE_T, TASK_ROLE_T, TASK_T
from ecs_composex.vpc import vpc_params, vpc_conditions

STATIC = 0


def import_env_variables(environment):
    """
    Function to import Docker compose env variables into ECS Env Variables
    :param environment: Environment variables as defined on the service definition
    :type environment: dict
    :return: list of Environment
    :type: list<troposphere.ecs.Environment>
    """
    env_vars = []
    for key in environment:
        if not isinstance(environment[key], str):
            env_vars.append(Environment(Name=key, Value=str(environment[key])))
        else:
            env_vars.append(Environment(Name=key, Value=environment[key]))
    return env_vars


def generate_port_mappings(ports):
    """
    Generates a port mapping from the Docker compose file.
    Given we are going to use AWS VPC mode, we are only considering the app port.

    :param ports: list of ports used by the service
    :type ports: list
    :returns: mappings, list of port mappings
    :rtype: list
    """
    mappings = []
    for port in ports:
        mappings.append(
            PortMapping(ContainerPort=port["target"], HostPort=port["target"])
        )
    return mappings


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

    keys = [
        "image",
        "ports",
        "environment",
        "configs",
        "labels",
        "command",
        "hostname",
        "entrypoint",
        "volumes",
        "deploy",
    ]
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
    entrypoint = None
    volumes = []
    ports = []
    links = []
    service = None

    def define_service_ports(self, ports):
        """Function to define common structure to ports

        :return: list of ports the service uses formatted according to dict
        :rtype: list
        """
        valid_keys = ["published", "target", "protocol", "mode"]
        service_ports = []
        for port in ports:
            if not isinstance(port, (str, dict, int)):
                raise TypeError(
                    "ports must be of types", dict, "or", list, "got", type(port)
                )
            if isinstance(port, str):
                service_ports.append(
                    {
                        "protocol": define_protocol(port),
                        "published": port.split(":")[0],
                        "target": port.split(":")[-1].split("/")[0].strip(),
                        "mode": "awsvpc",
                    }
                )
            elif isinstance(port, dict):
                if not set(port).issubset(valid_keys):
                    raise KeyError(f"Valid keys are", valid_keys, "got", port.keys())
                port["mode"] = "awsvpc"
                service_ports.append(port)
            elif isinstance(port, int):
                service_ports.append(
                    {
                        "protocol": "tcp",
                        "published": port,
                        "target": port,
                        "mode": "awsvpc",
                    }
                )
        LOG.debug(service_ports)
        self.ports = service_ports

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
        self.command = (
            definition["command"].strip() if KEYISSET("command", definition) else None
        )
        self.entrypoint = (
            definition["entrypoint"] if KEYISSET("entrypoint", definition) else None
        )
        self.sort_load_balancing()
        if KEYISSET("ports", definition):
            self.define_service_ports(definition["ports"])
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
    task_definition = None
    service = None

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

    def define_container_definition(self):
        """
        Generates the container definition
        """
        env_vars = import_env_variables(self.config.environment)
        mappings = generate_port_mappings(self.config.ports)
        if not mappings:
            mappings = Ref("AWS::NoValue")
        container = ContainerDefinition(
            # EntryPoint=If(ENTRY_CON, Ref('AWS::NoValue'), Split(' ', Ref(params.SERVICE_ENTRYPOINT))),
            Command=self.config.command.strip().split(";")
            if self.config.command
            else Ref("AWS::NoValue"),
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

    def add_task_defnition(self):
        """
        Function to generate and add the task definition with container definitions
        to the service template
        """
        add_parameters(
            self.template,
            [
                ecs_params.MEMORY_ALLOC,
                ecs_params.MEMORY_RES,
                ecs_params.SERVICE_NAME,
                ecs_params.SERVICE_IMAGE,
                ecs_params.FARGATE_CPU_RAM_CONFIG,
                ecs_params.TASK_CPU_COUNT,
            ],
        )
        self.template.add_condition(
            ecs_conditions.USE_FARGATE_CON_T, ecs_conditions.USE_FARGATE_CON
        )
        self.parameters.update(
            {
                ecs_params.SERVICE_IMAGE_T: self.config.image,
                ecs_params.SERVICE_NAME_T: self.service_name,
            }
        )
        self.task_definition = TaskDefinition(
            TASK_T,
            template=self.template,
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
            TaskRoleArn=GetAtt(self.template.resources[TASK_ROLE_T], "Arn"),
            ExecutionRoleArn=GetAtt(self.template.resources[EXEC_ROLE_T], "Arn"),
            ContainerDefinitions=[self.define_container_definition()],
            RequiresCompatibilities=["EC2", "FARGATE"],
            Tags=Tags(
                {
                    "Name": Ref(ecs_params.SERVICE_NAME),
                    "Environment": Ref("AWS::StackName"),
                }
            ),
        )

    def define_service_network_config(self, **kwargs):
        """Function to define microservice ingress.

        :return: tuple of the args for the Service() and the dependencies
        :rtype: tuple
        """
        add_service_default_sg(self.template)
        service_lbs = Ref("AWS::NoValue")
        registries = add_service_to_map(self)
        if not registries:
            registries = Ref("AWS::NoValue")
        service_attrs = {"LoadBalancers": service_lbs, "ServiceRegistries": registries}
        external_dependencies = []
        if not KEYISSET("AwsAzs", kwargs):
            raise KeyError(
                "Missing AwsAzs from options."
                "AZs are required to configure services networking"
            )
        if not self.config.ports:
            LOG.debug(f"{self.service_name} does not have any ports. No ingress necessary")
            return service_attrs, external_dependencies
        if self.config.use_alb or self.config.use_nlb:
            service_lb = define_service_load_balancing(self, **kwargs)
            service_attrs["LoadBalancers"] = service_lb[0]
            service_attrs["DependsOn"] = (
                service_lb[-1] if isinstance(service_lb[-1], list) else []
            )
        return service_attrs, external_dependencies

    def __init__(self, service_name, definition, content, **kwargs):
        """
        Function to initialize the Service object
        :param service_name:
        :param service:
        """
        self.definition = definition
        self.config = ServiceConfig(content, service_name, definition)
        LOG.debug(self.config)
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
        # self.network_settings = compile_network_settings(
        #     content, self.definition, self.service_name
        # )
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
        self.add_task_defnition()

        self.sgs = [ecs_params.SG_T, ecs_params.CLUSTER_SG_ID]
        self.network_config = self.define_service_network_config(**kwargs)
        generate_service_definition(
            self.template, self.network_settings, self.sgs, **self.network_config[0]
        )
        self.generate_service_template_outputs()
