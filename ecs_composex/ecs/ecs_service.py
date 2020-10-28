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

from ipaddress import IPv4Interface

from troposphere import (
    Join,
    Select,
    If,
    Tags,
    AWS_NO_VALUE,
    AWS_ACCOUNT_ID,
    AWS_STACK_NAME,
)
from troposphere import Ref, Sub, GetAtt
from troposphere import applicationautoscaling
from troposphere.ec2 import EIP, SecurityGroup
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import LoadBalancer as EcsLoadBalancer
from troposphere.ecs import (
    Service as EcsService,
    PlacementStrategy,
    AwsvpcConfiguration,
    NetworkConfiguration,
    DeploymentController,
)
from troposphere.ecs import ServiceRegistry
from troposphere.elasticloadbalancingv2 import (
    LoadBalancer,
    LoadBalancerAttributes,
    TargetGroup,
    TargetGroupAttribute,
    Listener,
    Action as ListenerAction,
    SubnetMapping,
)
from troposphere.servicediscovery import (
    DnsConfig as SdDnsConfig,
    Service as SdService,
    DnsRecord as SdDnsRecord,
    HealthCheckCustomConfig as SdHealthCheckCustomConfig,
    Instance as SdInstance,
)

from ecs_composex.common import keyisset, LOG, NONALPHANUM
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.dns.dns_conditions import CREATE_PUBLIC_NAMESPACE_CON_T
from ecs_composex.dns.dns_params import (
    PRIVATE_DNS_ZONE_NAME,
    PRIVATE_DNS_ZONE_ID,
    PUBLIC_DNS_ZONE_ID,
    PUBLIC_DNS_ZONE_NAME,
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


def generate_security_group_props(allowed_source, service_name):
    """
    Function to parse the allowed source and create the SG Opening options accordingly.

    :param dict allowed_source: The allowed source defined in configs
    :param str service_name:
    :return: security group ingress properties
    :rtype: dict
    """
    props = {
        "CidrIp": (
            allowed_source["ipv4"]
            if keyisset("ipv4", allowed_source)
            else Ref(AWS_NO_VALUE)
        ),
        "CidrIpv6": (
            allowed_source["ipv6"]
            if keyisset("ipv6", allowed_source)
            else Ref(AWS_NO_VALUE)
        ),
    }

    if keyisset("CidrIp", props) and isinstance(props["CidrIp"], str):
        try:
            IPv4Interface(props["CidrIp"])
        except Exception as error:
            LOG.error(
                f"Falty IP Address: {allowed_source} - ecs_service {service_name}"
            )
            raise ValueError("Not a valid IPv4 CIDR notation", props["CidrIp"], error)
    return props


def flatten_ip(ip_str):
    """
    Function to remove all non alphanum characters from IP CIDR notation

    :param ip_str:
    :rtype: str
    """
    return ip_str.replace(".", "").split("/")[0].strip()


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


def add_service_to_map(family):
    """
    Method to create a new Service into CloudMap to represent the current service and add entry into the registry
    """
    registries = []
    if not family.service_config.network.ports:
        return registries
    sd_service = SdService(
        f"{family.logical_name}DiscoveryService",
        template=family.template,
        Description=Ref(SERVICE_NAME),
        NamespaceId=Ref(PRIVATE_DNS_ZONE_ID),
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
        if (
            family.service_config.network.use_nlb()
            or family.service_config.network.use_alb()
        ):
            used_port = port["target"]
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
        "cpu": {"key": "cpu_target", "property": "ECSServiceAverageCPUUtilization"},
        "memory": {
            "key": "memory_target",
            "property": "ECSServiceAverageMemoryUtilization",
        },
        "targets": {
            "key": "tgt_targets_count",
            "property": "ALBRequestCountPerTarget",
        },
    }
    if config_key not in settings.keys():
        raise KeyError(config_key, "Is invalid. Expected one of", settings.keys())
    specification = applicationautoscaling.PredefinedMetricSpecification(
        PredefinedMetricType=settings[config_key]["property"]
    )
    # if config_key == "targets" and self.tgt_groups:
    #     specification = applicationautoscaling.PredefinedMetricSpecification(
    #         PredefinedMetricType=settings[config_key]["property"],
    #         ResourceLabel=GetAtt(self.tgt_groups[0], "TargetGroupFullName"),
    #     )
    # elif config_key == "targets" and not self.tgt_groups:
    #     raise ValueError(
    #         f"{self.family.logical_name} - Invalid target tracking for TGT Groups: No load-balancing defined"
    #     )
    return applicationautoscaling.TargetTrackingScalingPolicyConfiguration(
        DisableScaleIn=target_scaling_config["disable_scale_in"],
        ScaleInCooldown=target_scaling_config["scale_in_cooldown"],
        ScaleOutCooldown=target_scaling_config["scale_out_cooldown"],
        TargetValue=float(target_scaling_config[settings[config_key]["key"]]),
        PredefinedMetricSpecification=specification,
    )


def create_scalable_target(family):
    """
    Method to automatically create a scalable target
    """
    LOG.debug(family.service_config.scaling.range)
    if family.service_config.scaling.range:
        family.scalable_target = applicationautoscaling.ScalableTarget(
            ecs_params.SERVICE_SCALING_TARGET,
            template=family.template,
            MaxCapacity=family.service_config.scaling.range["max"],
            MinCapacity=family.service_config.scaling.range["min"],
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
        if keyisset("cpu_target", family.service_config.scaling.target_scaling):
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
        if keyisset("memory_target", family.service_config.scaling.target_scaling):
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
        if keyisset("tgt_targets_count", family.service_config.scaling.target_scaling):
            applicationautoscaling.ScalingPolicy(
                "ServiceAlbTargetTracking",
                template=family.template,
                ScalingTargetId=Ref(family.scalable_target),
                PolicyName="ALBTargetTrackingPolicy",
                PolicyType="TargetTrackingScaling",
                TargetTrackingScalingPolicyConfiguration=define_tracking_target_configuration(
                    family.service_config.scaling.target_scaling, "targets"
                ),
            )


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
        self.alb_sg = None
        self.links = []
        self.eips = []
        self.tgt_groups = []
        self.lbs = []
        self.service_attrs = {}
        self.dependencies = []
        self.network_settings = None
        self.ecs_service = None
        self.scalable_target = None
        self.parameters = {
            vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
            PRIVATE_DNS_ZONE_ID.title: Ref(PRIVATE_DNS_ZONE_ID),
            PRIVATE_DNS_ZONE_NAME.title: Ref(PRIVATE_DNS_ZONE_NAME),
            PUBLIC_DNS_ZONE_ID.title: Ref(PUBLIC_DNS_ZONE_ID),
            PUBLIC_DNS_ZONE_NAME.title: Ref(PUBLIC_DNS_ZONE_ID),
            vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
            ecs_params.CLUSTER_NAME_T: Ref(ecs_params.CLUSTER_NAME),
            ecs_params.SERVICE_NAME_T: family.name,
        }
        self.sgs = [ecs_params.SG_T]
        self.sg = add_service_default_sg(family.template)
        self.sgs.append(Ref(self.sg))
        self.define_service_ingress(settings, family)
        self.generate_service_definition(family)
        create_scalable_target(family)
        # self.generate_service_template_outputs()

    def add_self_ingress(self, sg):
        """
        Method to allow communications internally to the group on set ports
        :param sg:
        :return:
        """
        for port in self.config.ports:
            SecurityGroupIngress(
                f"AllowingMyselfToMyselfOnPort{port['published']}",
                template=self.template,
                FromPort=port["published"],
                ToPort=port["published"],
                IpProtocol=port["protocol"],
                GroupId=GetAtt(sg, "GroupId"),
                SourceSecurityGroupId=GetAtt(sg, "GroupId"),
                SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                Description=Sub(
                    f"Allowing traffic internally on port {port['published']}"
                ),
            )

    def add_aws_sources(self, sg):
        """
        Method to add ingress rules from other AWS Sources
        :param sg:
        :return:
        """
        allowed_keys = ["type", "id"]
        allowed_types = ["SecurityGroup", "PrefixList"]
        for source in self.config.aws_sources:
            if not all(key in allowed_keys for key in source.keys()):
                raise KeyError(
                    "Missing ingress properties. Got",
                    source.keys,
                    "Expected",
                    allowed_keys,
                )
            if not source["type"] in allowed_types:
                raise ValueError(
                    "Invalid type specified. Got",
                    source["type"],
                    "Allowed one of ",
                    allowed_types,
                )
            if source["type"] == "SecurityGroup":
                for port in self.config.ports:
                    SecurityGroupIngress(
                        f"From{NONALPHANUM.sub('', source['id'])}ToServiceOn{port['published']}",
                        template=self.template,
                        FromPort=port["published"],
                        ToPort=port["published"],
                        IpProtocol=port["protocol"],
                        GroupId=GetAtt(sg, "GroupId"),
                        SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                        SourceSecurityGroupId=source["id"],
                        Description=Sub(
                            f"From {source['id']} to ${{{SERVICE_NAME_T}}} on port {port['published']}"
                        ),
                    )
            elif source["type"] == "PrefixList":
                for port in self.config.ports:
                    SecurityGroupIngress(
                        f"From{NONALPHANUM.sub('', source['id'])}ToServiceOn{port['published']}",
                        template=self.template,
                        FromPort=port["published"],
                        ToPort=port["published"],
                        IpProtocol=port["protocol"],
                        GroupId=GetAtt(sg, "GroupId"),
                        SourcePrefixListId=source["id"],
                        Description=Sub(
                            f"From {source['id']} to ${{{SERVICE_NAME_T}}} on port {port['published']}"
                        ),
                    )

    def create_lb_ingress_rule(self, allowed_source, security_group, **props):
        for port in self.config.ports:
            if keyisset("source_name", allowed_source):
                title = f"From{allowed_source['source_name'].title()}Onto{port['published']}{port['protocol']}"
                description = Sub(
                    f"From {allowed_source['source_name'].title()} "
                    f"To {port['published']}{port['protocol']} for ${{{SERVICE_NAME_T}}}"
                )
            else:
                title = (
                    f"From{flatten_ip(allowed_source['ipv4'])}"
                    f"To{port['published']}{port['protocol']}"
                )
                description = Sub(
                    f"Public {port['published']}{port['protocol']}"
                    f" for ${{{SERVICE_NAME_T}}}"
                )
            SecurityGroupIngress(
                title,
                template=self.template,
                Description=description,
                GroupId=GetAtt(security_group, "GroupId"),
                IpProtocol=port["protocol"],
                FromPort=port["published"],
                ToPort=port["published"],
                **props,
            )

    def add_ext_sources_ingress(self, security_group):
        """
        Method to add ingress rules from external sources to a given Security Group (ie. ALB Security Group).
        If a list of IPs is found in the config['ext_sources'] part of the network section of configs for the service,
        then it will use that. If no IPv4 source is indicated, it will by default allow traffic from 0.0.0.0/0

        :param security_group: security group (object or title string) to add the rules to
        :type security_group: str or troposphere.ec2.SecurityGroup
        """
        if not self.config.ext_sources:
            self.config.ext_sources = [
                {"ipv4": "0.0.0.0/0", "protocol": -1, "source_name": "ANY"}
            ]

        for allowed_source in self.config.ext_sources:
            if not keyisset("ipv4", allowed_source) and not keyisset(
                "ipv6", allowed_source
            ):
                LOG.warn("No IPv4 or IPv6 set. Skipping")
                continue
            props = generate_security_group_props(
                allowed_source, self.family.logical_name
            )
            if props:
                LOG.debug(f"Adding {allowed_source} for ingress")
                self.create_lb_ingress_rule(allowed_source, security_group, **props)

    def add_public_ips(self, azs):
        """
        Method to add EIPs for each AZ and adds these to the service template.

        :param azs: list of AZs to deploy the EIPs to
        :type azs: list

        :return: list of troposphere.ec2.EIP
        :rtype: list
        """
        for az in azs:
            if isinstance(az, dict) and keyisset("ZoneName", az):
                az_name = NONALPHANUM.sub(
                    "", az["ZoneName"].title().replace("-", "").strip()
                )
            elif isinstance(az, str):
                az_name = NONALPHANUM.sub("", az)
            else:
                raise TypeError("az is neither a dict or a str. Got", type(az))
            self.eips.append(
                EIP(
                    f"EipPublicNlb{az_name}{self.family.logical_name}",
                    template=self.template,
                    Domain="vpc",
                )
            )

    def add_alb_sg(self, ports):
        """
        Method to add a security group for an AWS ALB (ELBv2, application type).

        :param ports: list of ports to add ingress from the ALB to ecs_service to
        :type ports: list of ports
        :return: The ALB's SG
        :rtype: troposphere.ec2.SecurityGroup
        """
        suffix = "Private"
        if self.config.is_public:
            suffix = "Public"
        self.alb_sg = SecurityGroup(
            f"AlbSecurityGroup{suffix}",
            template=self.template,
            GroupDescription=Sub(
                f"ALB SG for ${{{SERVICE_NAME_T}}} in ${{{ROOT_STACK_NAME_T}}}"
            ),
            VpcId=Ref(VPC_ID),
            Tags=Tags(
                {
                    "Name": Sub(
                        f"alb-sg-${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"
                    ),
                    "StackName": Ref(AWS_STACK_NAME),
                    "MicroserviceName": Ref(SERVICE_NAME),
                }
            ),
        )
        for port in ports:
            SecurityGroupIngress(
                f"FromAlbToServiceOnPort{port}",
                template=self.template,
                FromPort=port,
                ToPort=port,
                GroupId=GetAtt(SG_T, "GroupId"),
                SourceSecurityGroupId=GetAtt(self.alb_sg, "GroupId"),
                SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                IpProtocol="tcp",
            )

    def add_lb_listener(self, port, lb, tgt, target_port):
        """
        Method to add a new listener for a given Load Balancer and Target Group combination.

        :param port: port to add the listener for
        :type port: int
        :param lb: the loadbalancer the listener depends on
        :type lb: tropopshere.elasticloadbalancingv2.LoadBalancer
        :param tgt: the target group to associate
        :type tgt: troposphere.elasticloadbalancingv2.TargetGroup

        :return: listener
        :rtype: troposphere.elasticloadbalancingv2.Listener
        """
        suffix = "Private"
        if self.config.is_public:
            suffix = "Public"
        listener = Listener(
            f"{self.config.lb_type.title()}{suffix}ListenerPort{port}To{target_port}",
            template=self.template,
            DependsOn=[lb],
            DefaultActions=[ListenerAction(Type="forward", TargetGroupArn=Ref(tgt))],
            LoadBalancerArn=Ref(lb),
            Port=port,
            Protocol="TCP" if self.config.lb_type == "network" else "HTTP",
        )
        return listener

    def add_target_group(self, port, lb):
        """
        Method to generate the TargetGroups based on the ports of the service.

        :param port: the port to add the targetgroup for
        :type port: int
        :param lb: the loadbalancer the targetgroup will be bound to
        :type lb: troposphere.elasticloadbalancingv2.LoadBalancer
        :return: target group
        :rtype: troposphere.elasticloadbalancingv2.TargetGroup
        """
        suffix = "Private"
        if self.config.is_public:
            suffix = "Public"
        tgt = TargetGroup(
            f"{self.config.lb_type.title()}{suffix}TargetGroupPort{port}".strip(),
            template=self.template,
            DependsOn=[lb],
            VpcId=Ref(VPC_ID),
            Port=port,
            Protocol="TCP" if self.config.lb_type == "network" else "HTTP",
            TargetType="ip",
            HealthCheckIntervalSeconds=10,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=2,
            TargetGroupAttributes=[
                TargetGroupAttribute(
                    Key="deregistration_delay.timeout_seconds", Value="10"
                )
            ],
            Tags=Tags(
                {
                    "Name": Sub(f"${{{SERVICE_NAME_T}}}-{port}"),
                    "StackName": Ref(AWS_STACK_NAME),
                    "StackId": Ref("AWS::StackId"),
                    "MicroserviceName": Ref(SERVICE_NAME_T),
                }
            ),
        )
        self.tgt_groups.append(tgt)
        return tgt

    def add_load_balancer(self, settings):
        """
        Method to add LB to template

        :return: loadbalancer
        :rtype: troposphere.elasticloadbalancingv2.LoadBalancer
        """
        if self.config.is_public and self.config.use_nlb():
            self.add_public_ips(settings.aws_azs)

        no_value = Ref(AWS_NO_VALUE)
        public_mapping = define_public_mapping(self.eips, settings.aws_azs)
        if self.config.ingress_mappings and self.config.use_alb():
            self.add_alb_sg(self.config.ingress_mappings.keys())
            lb_sg = [Ref(self.alb_sg)]
        else:
            lb_sg = no_value

        loadbalancer = LoadBalancer(
            f"Microservice{self.config.lb_type.title()}LB",
            template=self.template,
            Scheme="internet-facing" if self.config.is_public else "internal",
            LoadBalancerAttributes=[
                LoadBalancerAttributes(
                    Key="load_balancing.cross_zone.enabled", Value="true"
                )
            ]
            if self.config.use_nlb()
            else no_value,
            SecurityGroups=lb_sg if self.config.use_alb() else no_value,
            Type=self.config.lb_type,
            Tags=Tags(
                {
                    "Name": Sub(f"${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"),
                    "StackName": Ref(AWS_STACK_NAME),
                    "MicroserviceName": Ref(SERVICE_NAME),
                }
            ),
        )
        if self.config.is_public and self.config.use_alb():
            setattr(loadbalancer, "Subnets", Ref(PUBLIC_SUBNETS))
        elif self.config.is_public and self.config.use_nlb():
            setattr(loadbalancer, "SubnetMappings", public_mapping)
            setattr(loadbalancer, "Subnets", Ref(AWS_NO_VALUE))
        elif not self.config.is_public:
            setattr(loadbalancer, "Subnets", Ref(vpc_params.APP_SUBNETS))
        if self.config.is_public:
            sd_service = SdService(
                f"{self.resource_name}PublicDiscoveryService",
                template=self.template,
                Description=Ref(SERVICE_NAME),
                Condition=CREATE_PUBLIC_NAMESPACE_CON_T,
                NamespaceId=Ref(PUBLIC_DNS_ZONE_ID),
                HealthCheckCustomConfig=SdHealthCheckCustomConfig(FailureThreshold=1.0),
                DnsConfig=SdDnsConfig(
                    RoutingPolicy="WEIGHTED",
                    NamespaceId=Ref(AWS_NO_VALUE),
                    DnsRecords=[SdDnsRecord(TTL="15", Type="A")],
                ),
                Name=If(USE_HOSTNAME_CON_T, Ref(SERVICE_HOSTNAME), Ref(SERVICE_NAME)),
            )
            SdInstance(
                f"{self.resource_name}PublicLB",
                template=self.template,
                Condition=CREATE_PUBLIC_NAMESPACE_CON_T,
                ServiceId=GetAtt(sd_service, "Id"),
                InstanceAttributes={
                    "AWS_ALIAS_DNS_NAME": GetAtt(loadbalancer, "DNSName")
                },
            )
        if self.config.use_alb() and self.alb_sg:
            self.add_ext_sources_ingress(self.alb_sg)
        elif self.config.use_nlb():
            self.add_ext_sources_ingress(SG_T)
        self.lbs.append(loadbalancer)
        return loadbalancer

    def add_service_load_balancer(self, settings):
        """
        Method to add all ELBv2 resources for a microservice

        :return: service_lbs, depends_on
        :rtype: tuple
        """
        service_lbs = []
        tgt_groups = []
        depends_on = []
        service_lb = self.add_load_balancer(settings)
        depends_on.append(service_lb.title)
        for port_target in self.config.ingress_mappings:
            tgt = self.add_target_group(port_target, service_lb)
            for source in self.config.ingress_mappings[port_target]:
                listener = self.add_lb_listener(source, service_lb, tgt, port_target)
                depends_on.append(listener.title)
            tgt_groups.append(tgt)
            depends_on.append(tgt.title)
            service_lbs.append(
                EcsLoadBalancer(
                    TargetGroupArn=Ref(tgt),
                    ContainerPort=tgt.Port,
                    ContainerName=self.config.resource.container_name,
                )
            )
        return service_lbs, depends_on

    def generate_service_template_outputs(self):
        """
        Function to generate the Service template outputs
        """
        self.template.add_output(
            ComposeXOutput(
                self.resource_name,
                [
                    (
                        ecs_params.SERVICE_GROUP_ID_T,
                        "GroupId",
                        GetAtt(ecs_params.SG_T, "GroupId"),
                    )
                ],
                duplicate_attr=True,
            ).outputs
        )

    def update_for_service_mesh(self):
        """
        Method to create the AppMesh
        """

    def define_service_ingress(self, settings, family):
        """
        Function to define microservice ingress.

        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        :param family:
        """
        service_lbs = Ref(AWS_NO_VALUE)
        registries = add_service_to_map(family)
        if not registries:
            registries = Ref(AWS_NO_VALUE)
        self.service_attrs = {
            "LoadBalancers": service_lbs,
            "ServiceRegistries": registries,
        }
        # external_dependencies = []
        # if not self.config.ports:
        #     LOG.debug(
        #         f"{self.family.logical_name} does not have any ports. No ingress necessary"
        #     )
        #     return self.service_attrs, external_dependencies
        # if self.config.use_alb() or self.config.use_nlb():
        #     service_lb = self.add_service_load_balancer(settings)
        #     self.service_attrs["LoadBalancers"] = service_lb[0]
        #     self.service_attrs["DependsOn"] = (
        #         service_lb[-1] if isinstance(service_lb[-1], list) else []
        #     )
        #     self.service_attrs["HealthCheckGracePeriodSeconds"] = (
        #         Ref(ecs_params.ELB_GRACE_PERIOD)
        #         if self.service_attrs["LoadBalancers"]
        #         else Ref(AWS_NO_VALUE)
        #     )
        #     if self.config.use_alb() and self.config.aws_sources:
        #         self.add_aws_sources(self.alb_sg)
        # elif (
        #     self.config.use_nlb() and self.config.aws_sources
        # ) or self.config.aws_sources:
        #     self.add_aws_sources(self.sg)
        # if self.config.ingress_from_self:
        #     self.add_self_ingress(self.sg)

    def generate_service_definition(self, family):
        """
        Function to generate the Service definition.
        This is the last step in defining the service, after all other settings have been prepared.

        :param ecs_composex.common.compose_services.ComposeFamily family:
        """
        service_sgs = [
            Ref(sg) for sg in self.sgs if not isinstance(sg, (Ref, Sub, If, GetAtt))
        ]
        service_sgs += [sg for sg in self.sgs if isinstance(sg, (Ref, Sub, If, GetAtt))]
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
            **self.service_attrs,
        )
        family.service_definition = self.ecs_service
