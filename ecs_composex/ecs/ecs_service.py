#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to build the ECS Service Definition
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import (
    AWS_NO_VALUE,
    AWS_STACK_NAME,
    GetAtt,
    If,
    Join,
    Ref,
    Select,
    Sub,
    Tags,
    applicationautoscaling,
)
from troposphere.ec2 import SecurityGroup
from troposphere.ecs import AwsvpcConfiguration
from troposphere.ecs import DeploymentCircuitBreaker as EcsDeploymentCircuitBreaker
from troposphere.ecs import (
    DeploymentConfiguration,
    DeploymentController,
    NetworkConfiguration,
    PlacementStrategy,
)
from troposphere.ecs import Service as EcsService
from troposphere.ecs import ServiceRegistry
from troposphere.elasticloadbalancingv2 import SubnetMapping
from troposphere.servicediscovery import DnsConfig as SdDnsConfig
from troposphere.servicediscovery import DnsRecord as SdDnsRecord
from troposphere.servicediscovery import (
    HealthCheckCustomConfig as SdHealthCheckCustomConfig,
)
from troposphere.servicediscovery import Service as SdService

from ecs_composex.common import LOG
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.dns.dns_conditions import PRIVATE_NAMESPACE_CON_T
from ecs_composex.dns.dns_params import PRIVATE_NAMESPACE_ID
from ecs_composex.ecs import ecs_conditions, ecs_params
from ecs_composex.ecs.ecs_conditions import USE_HOSTNAME_CON_T, use_external_lt_con
from ecs_composex.ecs.ecs_params import (
    SERVICE_HOSTNAME,
    SERVICE_NAME,
    SERVICE_NAME_T,
    SG_T,
)
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_params import PUBLIC_SUBNETS, VPC_ID


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


def define_public_mapping(eips, azs):
    """Function to get the public mapping for NLB

    :param eips: list of EIPSs
    :type eips: list(troposphere.ec2.EIP)
    :param azs: list of AZs to created EIPs into
    :type azs: list

    :return: list
    """
    public_mappings = []
    if eips:
        public_mappings = [
            SubnetMapping(
                AllocationId=GetAtt(eip, "AllocationId"),
                SubnetId=Select(count, Ref(PUBLIC_SUBNETS)),
            )
            for count, eip in enumerate(eips)
        ]
    elif azs:
        public_mappings = [
            SubnetMapping(SubnetId=Select(count, Ref(PUBLIC_SUBNETS)))
            for count in range(len(azs))
        ]
    return public_mappings


def add_service_to_map(family, settings):
    """
    Method to create a new Service into CloudMap to represent the current service and add entry into the registry
    """
    registries = []
    if not family.service_config.network.ports:
        LOG.warning(
            f"No ports were defined for the services in {family.logical_name}."
            " Not creating a service in CloudMap"
        )
        return registries
    elif not family.service_config.network.use_cloudmap and not settings.use_appmesh:
        return registries
    sd_service = SdService(
        f"{family.logical_name}DiscoveryService",
        template=family.template,
        Condition=PRIVATE_NAMESPACE_CON_T,
        Description=Ref(SERVICE_NAME),
        NamespaceId=Ref(PRIVATE_NAMESPACE_ID),
        HealthCheckCustomConfig=SdHealthCheckCustomConfig(FailureThreshold=1.0),
        DnsConfig=SdDnsConfig(
            RoutingPolicy="MULTIVALUE",
            NamespaceId=Ref(AWS_NO_VALUE),
            DnsRecords=[
                SdDnsRecord(TTL="15", Type="A"),
                SdDnsRecord(TTL="15", Type="SRV"),
            ],
        ),
        Name=If(USE_HOSTNAME_CON_T, Ref(SERVICE_HOSTNAME), Ref(SERVICE_NAME)),
    )
    for port in family.service_config.network.ports:
        used_port = port["published"]
        registry = ServiceRegistry(
            f"ServiceRegistry{used_port}",
            RegistryArn=GetAtt(sd_service, "Arn"),
            Port=used_port,
        )
        registries.append(registry)
        break
    return registries


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
                    GetAtt(ecs_params.SG_T, "GroupId"),
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


def define_service_ingress(family, settings):
    """
    Function to define microservice ingress.

    :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
    :param family:
    """
    service_lbs = []
    registries = add_service_to_map(family, settings)
    if not registries:
        registries = Ref(AWS_NO_VALUE)
    service_attrs = {
        "LoadBalancers": service_lbs,
        "ServiceRegistries": If(PRIVATE_NAMESPACE_CON_T, registries, Ref(AWS_NO_VALUE)),
    }
    return service_attrs


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

    :cvar list links: the links used for DependsOn of the service stack
    :cvar list dependencies: list of services used for the DependsOn of the service stack
    :cvar ServiceConfig config: The service configuration
    :cvar troposphere.ecs.TaskDefinition task_definition: The service task definition for ECS
    :cvar list<troposphere.ec2.EIP> eips: list of AWS EC2 EIPs which are used for the public NLB
    :cvar dict service_attrs: Attributes defined to expand the troposphere.ecs.ServiceDefinition from prior settings.
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

        ingress_props = define_service_ingress(family, settings)
        self.lbs = ingress_props["LoadBalancers"]
        self.registries = ingress_props["ServiceRegistries"]

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
                        Subnets=Ref(AWS_NO_VALUE),
                        SecurityGroups=Ref(AWS_NO_VALUE),
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
