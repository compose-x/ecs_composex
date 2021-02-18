# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

from troposphere import (
    Join,
    Select,
    If,
    Tags,
    AWS_NO_VALUE,
    AWS_STACK_NAME,
)
from troposphere import Ref, Sub, GetAtt
from troposphere import applicationautoscaling
from troposphere.ec2 import SecurityGroup
from troposphere.ecs import (
    Service as EcsService,
    PlacementStrategy,
    AwsvpcConfiguration,
    NetworkConfiguration,
    DeploymentController,
)
from troposphere.ecs import ServiceRegistry
from troposphere.elasticloadbalancingv2 import (
    SubnetMapping,
)
from troposphere.servicediscovery import (
    DnsConfig as SdDnsConfig,
    Service as SdService,
    DnsRecord as SdDnsRecord,
    HealthCheckCustomConfig as SdHealthCheckCustomConfig,
)

from ecs_composex.common import keyisset, LOG
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.dns.dns_params import (
    PRIVATE_DNS_ZONE_NAME,
    PRIVATE_DNS_ZONE_ID,
    PUBLIC_DNS_ZONE_ID,
    PUBLIC_DNS_ZONE_NAME,
    PRIVATE_NAMESPACE_ID,
)
from ecs_composex.dns.dns_conditions import (
    PRIVATE_ZONE_ID_CON_T,
    PRIVATE_NAMESPACE_CON_T,
)
from ecs_composex.ecs import ecs_params, ecs_conditions
from ecs_composex.ecs.ecs_conditions import USE_HOSTNAME_CON_T
from ecs_composex.ecs.ecs_params import SERVICE_NAME, SERVICE_HOSTNAME
from ecs_composex.ecs.ecs_params import (
    SERVICE_NAME_T,
    SG_T,
)
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_params import VPC_ID, PUBLIC_SUBNETS


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


def add_service_default_sg(template):
    """
    Adds a default security group for the microservice.
    """
    sg = template.add_resource(
        SecurityGroup(
            SG_T,
            GroupDescription=If(
                USE_STACK_NAME_CON_T,
                Sub(f"SG for ${{{SERVICE_NAME_T}}} - ${{AWS::StackName}}"),
                Sub(f"SG for ${{{SERVICE_NAME_T}}} - ${{{ROOT_STACK_NAME_T}}}"),
            ),
            Tags=Tags(
                {
                    "Name": If(
                        USE_STACK_NAME_CON_T,
                        Sub(f"${{{SERVICE_NAME_T}}}-${{AWS::StackName}}"),
                        Sub(f"${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"),
                    ),
                    "StackName": Ref(AWS_STACK_NAME),
                    "MicroserviceName": Ref(SERVICE_NAME),
                }
            ),
            VpcId=Ref(VPC_ID),
        )
    )
    return sg


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


def define_tracking_target_configuration(target_scaling_config, config_key):
    """
    Function to create the configuration for target tracking scaling

    :param dict target_scaling_config:
    :param str config_key:
    :return:
    """
    settings = {
        "cpu": {"key": "CpuTarget", "property": "ECSServiceAverageCPUUtilization"},
        "memory": {
            "key": "MemoryTarget",
            "property": "ECSServiceAverageMemoryUtilization",
        },
        "targets": {
            "key": "TgtTargetsCount",
            "property": "ALBRequestCountPerTarget",
        },
    }
    if config_key not in settings.keys():
        raise KeyError(config_key, "Is invalid. Expected one of", settings.keys())
    specification = applicationautoscaling.PredefinedMetricSpecification(
        PredefinedMetricType=settings[config_key]["property"]
    )

    return applicationautoscaling.TargetTrackingScalingPolicyConfiguration(
        DisableScaleIn=target_scaling_config["DisableScaleIn"],
        ScaleInCooldown=target_scaling_config["ScaleInCooldown"],
        ScaleOutCooldown=target_scaling_config["ScaleOutCooldown"],
        TargetValue=float(target_scaling_config[settings[config_key]["key"]]),
        PredefinedMetricSpecification=specification,
    )


def create_scalable_target(family):
    """
    Method to automatically create a scalable target
    """
    LOG.debug(family.service_config.scaling.scaling_range)
    if family.service_config.scaling.scaling_range:
        family.scalable_target = applicationautoscaling.ScalableTarget(
            ecs_params.SERVICE_SCALING_TARGET,
            template=family.template,
            MaxCapacity=family.service_config.scaling.scaling_range["max"],
            MinCapacity=family.service_config.scaling.scaling_range["min"],
            ScalableDimension="ecs:service:DesiredCount",
            ServiceNamespace="ecs",
            RoleARN=Sub(
                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/"
                "ecs.application-autoscaling.${AWS::URLSuffix}/"
                "AWSServiceRoleForApplicationAutoScaling_ECSService"
            ),
            ResourceId=Sub(
                f"service/${{{ecs_params.CLUSTER_NAME.title}}}/${{{family.service_definition.title}.Name}}"
            ),
            SuspendedState=applicationautoscaling.SuspendedState(
                DynamicScalingInSuspended=False
            ),
        )
    if family.scalable_target and family.service_config.scaling.target_scaling:
        if keyisset("CpuTarget", family.service_config.scaling.target_scaling):
            applicationautoscaling.ScalingPolicy(
                "ServiceCpuTrackingPolicy",
                template=family.template,
                ScalingTargetId=Ref(family.scalable_target),
                PolicyName="CpuTrackingScalingPolicy",
                PolicyType="TargetTrackingScaling",
                TargetTrackingScalingPolicyConfiguration=define_tracking_target_configuration(
                    family.service_config.scaling.target_scaling, "cpu"
                ),
            )
        if keyisset("MemoryTarget", family.service_config.scaling.target_scaling):
            applicationautoscaling.ScalingPolicy(
                "ServiceMemoryTrackingPolicy",
                template=family.template,
                ScalingTargetId=Ref(family.scalable_target),
                PolicyName="MemoryTrackingScalingPolicy",
                PolicyType="TargetTrackingScaling",
                TargetTrackingScalingPolicyConfiguration=define_tracking_target_configuration(
                    family.service_config.scaling.target_scaling, "memory"
                ),
            )


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
                (ecs_params.TASK_T, ecs_params.TASK_T, Ref(family.task_definition)),
                (
                    vpc_params.APP_SUBNETS,
                    vpc_params.APP_SUBNETS.title,
                    Join(",", Ref(vpc_params.APP_SUBNETS)),
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
        self.network_settings = None
        self.ecs_service = None
        self.scalable_target = None
        family.stack_parameters.update({ecs_params.SERVICE_NAME_T: family.name})
        self.sgs = []
        self.sg = add_service_default_sg(family.template)
        self.sgs.append(Ref(self.sg))
        self.generate_service_definition(family, settings)
        create_scalable_target(family)
        generate_service_template_outputs(family)

    def generate_service_definition(self, family, settings):
        """
        Function to generate the Service definition.
        This is the last step in defining the service, after all other settings have been prepared.

        :param ecs_composex.common.compose_services.ComposeFamily family:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        service_sgs = [
            Ref(sg) for sg in self.sgs if not isinstance(sg, (Ref, Sub, If, GetAtt))
        ]
        service_sgs += [sg for sg in self.sgs if isinstance(sg, (Ref, Sub, If, GetAtt))]
        attrs = define_service_ingress(family, settings)
        self.ecs_service = EcsService(
            ecs_params.SERVICE_T,
            template=family.template,
            Cluster=Ref(ecs_params.CLUSTER_NAME),
            DeploymentController=DeploymentController(
                Type=Ref(ecs_params.ECS_CONTROLLER)
            ),
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
            SchedulingStrategy=If(
                ecs_conditions.USE_FARGATE_CON_T,
                "REPLICA",
                If(
                    ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
                    "REPLICA",
                    "DAEMON",
                ),
            ),
            PlacementStrategies=If(
                ecs_conditions.USE_FARGATE_CON_T,
                Ref(AWS_NO_VALUE),
                define_placement_strategies(),
            ),
            NetworkConfiguration=NetworkConfiguration(
                AwsvpcConfiguration=AwsvpcConfiguration(
                    Subnets=Ref(vpc_params.APP_SUBNETS), SecurityGroups=service_sgs
                )
            ),
            TaskDefinition=Ref(family.task_definition),
            LaunchType=If(
                ecs_conditions.USE_CLUSTER_CAPACITY_PROVIDERS_CON_T,
                Ref(AWS_NO_VALUE),
                Ref(ecs_params.LAUNCH_TYPE),
            ),
            Tags=Tags(
                {
                    "Name": Ref(ecs_params.SERVICE_NAME),
                    "StackName": Ref(AWS_STACK_NAME),
                }
            ),
            PropagateTags="SERVICE",
            PlatformVersion=Ref(ecs_params.FARGATE_VERSION),
            **attrs,
        )
        family.service_definition = self.ecs_service
