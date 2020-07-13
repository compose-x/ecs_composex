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

import re

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
from troposphere.ecs import TaskDefinition
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
)

from ecs_composex.common import add_parameters
from ecs_composex.common import keyisset, LOG
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.ecs import ecs_params, ecs_conditions
from ecs_composex.ecs.docker_tools import find_closest_fargate_configuration
from ecs_composex.ecs.ecs_conditions import USE_HOSTNAME_CON_T
from ecs_composex.ecs.ecs_container import Container
from ecs_composex.ecs.ecs_iam import add_service_roles
from ecs_composex.ecs.ecs_params import NETWORK_MODE, EXEC_ROLE_T, TASK_ROLE_T, TASK_T
from ecs_composex.ecs.ecs_params import SERVICE_NAME, SERVICE_HOSTNAME
from ecs_composex.ecs.ecs_params import (
    SERVICE_NAME_T,
    SG_T,
)
from ecs_composex.ecs.ecs_aws_sidecars import define_xray_container
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_conditions import USE_VPC_MAP_ID_CON_T
from ecs_composex.vpc.vpc_params import VPC_ID, PUBLIC_SUBNETS
from ecs_composex.vpc.vpc_params import VPC_MAP_ID

CIDR_REG = r"""((((((([0-9]{1}\.))|([0-9]{2}\.)|
(1[0-9]{2}\.)|(2[0-5]{2}\.)))){3})(((((([0-9]{1}))|
([0-9]{2})|(1[0-9]{2})|(2[0-5]{2}))))){1,3})\/(([0-9])|([1-2][0-9])|((3[0-2])))$"""
CIDR_PAT = re.compile(CIDR_REG)


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


class Task(object):
    """
    Class to handle the Task definition building and parsing along with the service config.
    """

    def __init__(self, template, containers_config, family_parameters):
        """
        Init method
        """
        self.family_config = None
        self.containers = []
        self.containers_config = containers_config
        self.stack_parameters = {}
        self.sort_container_configs(template, containers_config)
        add_service_roles(template, self.family_config)
        if self.family_config.use_xray:
            self.containers.append(define_xray_container())
            add_parameters(template, [ecs_params.XRAY_IMAGE])
            self.stack_parameters.update(
                {ecs_params.XRAY_IMAGE_T: Ref(ecs_params.XRAY_IMAGE)}
            )
        self.set_task_compute_parameter()
        self.set_task_definition(template)

    def set_task_definition(self, template):
        """
        Method to set or update the task definition

        :param troposphere.Template template: the template to add the definition to
        """
        self.definition = TaskDefinition(
            TASK_T,
            template=template,
            Cpu=ecs_params.FARGATE_CPU,
            Memory=ecs_params.FARGATE_RAM,
            NetworkMode=NETWORK_MODE,
            Family=Ref(ecs_params.SERVICE_NAME),
            TaskRoleArn=GetAtt(TASK_ROLE_T, "Arn"),
            ExecutionRoleArn=GetAtt(EXEC_ROLE_T, "Arn"),
            ContainerDefinitions=self.containers,
            RequiresCompatibilities=["EC2", "FARGATE"],
            Tags=Tags(
                {
                    "Name": Ref(ecs_params.SERVICE_NAME),
                    "Environment": Ref(AWS_STACK_NAME),
                }
            ),
        )

    def add_appmesh_envoy(self, envoy_container, parameters):
        """
        Method to replay and update the definition to add the Envoy sidecar

        :param ecs_composex.ecs.ecs_container.Conatainer envoy_container: The container to add to the definition
        :param dict parameters: The stack parameters to update.
        """

    def sort_container_configs(self, template, containers_config):
        """
        Method to sort out the containers dependencies and create the containers definitions based on the configs.
        :return:
        """
        config_key = "config"
        priority_key = "priority"
        services_names = list(containers_config.keys())
        unordered = []
        for service_name in services_names:
            service_config = containers_config[service_name][config_key]
            if service_config.depends_on and any(
                i in services_names for i in service_config.depends_on
            ):
                for count, dependency in enumerate(service_config.depends_on):
                    containers_config[dependency][priority_key] += 1
                    containers_config[dependency]["config"].essential = False
                    service_config.family_dependents.append(
                        {
                            "ContainerName": dependency,
                            "Condition": "START"
                            if not containers_config[dependency]["config"].healthcheck
                            else "HEALTHY",
                        }
                    )
                    service_config.depends_on.pop(count)
        for service in containers_config:
            unordered.append(containers_config[service])
        ordered_containers_config = sorted(unordered, key=lambda i: i["priority"])
        ordered_containers_config[0]["config"].essential = True
        for service_config in ordered_containers_config:
            container = Container(
                template,
                service_config["config"].resource_name,
                service_config["definition"],
                service_config["config"],
            )
            self.containers.append(container.definition)
            self.stack_parameters.update(container.stack_parameters)
            if self.family_config is None:
                self.family_config = service_config["config"]
            else:
                self.family_config += service_config["config"]

    def set_task_compute_parameter(self):
        """
        Method to update task parameter for CPU/RAM profile
        """
        tasks_cpu = 0
        tasks_ram = 0
        for container in self.containers:
            if isinstance(container.Cpu, int):
                tasks_cpu += container.Cpu
            if isinstance(container.Memory, int):
                tasks_ram += container.Memory
            elif isinstance(container.Memory, Ref) and isinstance(
                container.MemoryReservation, int
            ):
                tasks_ram += container.MemoryReservation
        LOG.debug(f"CPU: {tasks_cpu}, RAM: {tasks_ram}")
        if tasks_cpu > 0 and tasks_ram > 0:
            cpu_ram = find_closest_fargate_configuration(tasks_cpu, tasks_ram, True)
            self.stack_parameters.update({ecs_params.FARGATE_CPU_RAM_CONFIG_T: cpu_ram})


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

    def __init__(self, template, family_name, task_definition, config, settings):
        """
        Function to initialize the Service object
        :param family_name: Name of the service
        :type family_name: str
        :param definition: the service definition as defined in compose file
        :type definition: dict
        :param kwargs: unordered arguments
        :type kwargs: dict
        """
        self.template = template
        self.config = config
        self.task = task_definition
        self.links = []
        self.eips = []
        self.service_attrs = None
        self.dependencies = []
        self.network_settings = None
        self.ecs_service = None
        self.service_name = (
            config.resource_name if config.family_name is None else config.family_name
        )
        self.resource_name = (
            config.resource_name if config.family_name is None else config.family_name
        )
        self.parameters = {
            vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
            vpc_params.VPC_MAP_ID_T: Ref(vpc_params.VPC_MAP_ID),
            vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
            ecs_params.CLUSTER_NAME_T: Ref(ecs_params.CLUSTER_NAME),
            vpc_params.VPC_MAP_DNS_ZONE_T: Ref(vpc_params.VPC_MAP_DNS_ZONE),
        }
        if config.family_name is not None:
            self.parameters.update({ecs_params.SERVICE_NAME_T: config.family_name})
        else:
            self.parameters.update({ecs_params.SERVICE_NAME_T: family_name})
        self.sgs = [ecs_params.SG_T]
        self.sgs.append(
            If(
                ecs_conditions.USE_CLUSTER_SG_CON_T,
                Ref(ecs_params.CLUSTER_SG_ID),
                Ref("AWS::NoValue"),
            )
        )
        self.define_service_ingress(settings)
        self.generate_service_definition(self.task.definition)
        self.generate_service_template_outputs()

    def add_service_default_sg(self):
        """
        Adds a default security group for the microservice.
        """
        self.template.add_resource(
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

    def add_service_to_map(self):
        """
        Method to create a new Service into CloudMap to represent the current service and add entry into the registry
        """
        sd_service = SdService(
            f"{self.resource_name}DiscoveryService",
            template=self.template,
            Condition=USE_VPC_MAP_ID_CON_T,
            Description=Ref(SERVICE_NAME),
            NamespaceId=Ref(VPC_MAP_ID),
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
        registries = []
        for port in self.config.ports:
            registry = ServiceRegistry(
                f"ServiceRegistry{port['published']}",
                RegistryArn=GetAtt(sd_service, "Arn"),
                Port=port["published"],
            )
            registries.append(registry)
            break
        return registries

    def add_lb_to_service_ingress(self, lb_sg, service_sg):
        """
        Method to add ingress rules between the LB and the microservice according to the ports defined by the service.

        :param lb_sg: Load Balancer security group
        :type lb_sg: troposphere.ec2.SecurityGroup
        :param service_sg: security group of the microservice
        :type service_sg: str or troposphere.ec2.SecurityGroup
        """
        LOG.debug(f"Adding ALB ingress to ecs_service")
        for port in self.config.ports:
            SecurityGroupIngress(
                f"From{self.config.lb_type.title()}ToServicePort{port['target']}",
                template=self.template,
                FromPort=port["target"],
                ToPort=port["target"],
                IpProtocol=port["protocol"],
                GroupId=GetAtt(service_sg, "GroupId"),
                SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                SourceSecurityGroupId=GetAtt(lb_sg, "GroupId"),
                Description=Sub(
                    f"From LB to ${{{SERVICE_NAME_T}}} on port {port['target']}"
                ),
            )

    def add_public_security_group_ingress(self, security_group):
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
            props = {}
            if not keyisset("ipv4", allowed_source) and not keyisset(
                "ipv6", allowed_source
            ):
                LOG.warn("No IPv4 or IPv6 set. Skipping")
                continue

            props["CidrIp"] = (
                allowed_source["ipv4"]
                if keyisset("ipv4", allowed_source)
                else Ref(AWS_NO_VALUE)
            )
            props["CidrIpv6"] = (
                allowed_source["ipv6"]
                if keyisset("ipv6", allowed_source)
                else Ref(AWS_NO_VALUE)
            )

            if (
                keyisset("CidrIp", props)
                and isinstance(props["CidrIp"], str)
                and not CIDR_PAT.match(props["CidrIp"])
            ):
                LOG.error(
                    f"Falty IP Address: {allowed_source} - ecs_service {self.service_name}"
                )
                raise ValueError(
                    "Not a valid IPv4 CIDR notation",
                    props["CidrIp"],
                    "Expected",
                    CIDR_REG,
                )

            LOG.debug(f"Adding {allowed_source} for ingress")

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
                        "To{port['published']}{port['protocol']}"
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

    def add_public_ips(self, azs):
        """
        Method to add EIPs for each AZ and adds these to the service template.

        :param azs: list of AZs to deploy the EIPs to
        :type azs: list

        :return: list of troposphere.ec2.EIP
        :rtype: list
        """
        for az in azs:
            self.eips.append(
                EIP(
                    f"EipPublicNlb{az.replace('-', '').strip()}{self.service_name}",
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
        sg = SecurityGroup(
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
                SourceSecurityGroupId=GetAtt(sg, "GroupId"),
                SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
                IpProtocol="tcp",
            )
        return sg

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
        return tgt

    def add_load_balancer(self, settings):
        """
        Method to add LB to template

        :return: loadbalancer
        :rtype: troposphere.elasticloadbalancingv2.LoadBalancer
        """
        alb_sg = None
        if self.config.is_public and self.config.use_nlb():
            self.add_public_ips(settings.aws_azs)

        no_value = Ref(AWS_NO_VALUE)
        public_mapping = define_public_mapping(self.eips, settings.aws_azs)
        if self.config.ingress_mappings and self.config.use_alb():
            alb_sg = self.add_alb_sg(self.config.ingress_mappings.keys())
            # self.add_lb_to_service_ingress(alb_sg, SG_T)
            lb_sg = [Ref(alb_sg)]
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
            if self.config.lb_type == "network"
            else no_value,
            SecurityGroups=lb_sg,
            SubnetMappings=public_mapping
            if self.config.is_public and self.config.use_nlb()
            else no_value,
            Subnets=Ref(PUBLIC_SUBNETS)
            if self.config.is_public and self.config.use_alb()
            else Ref(vpc_params.APP_SUBNETS),
            Type=self.config.lb_type,
            Tags=Tags(
                {
                    "Name": Sub(f"${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"),
                    "StackName": Ref(AWS_STACK_NAME),
                    "MicroserviceName": Ref(SERVICE_NAME),
                }
            ),
        )
        if self.config.is_public:
            if self.config.use_alb() and alb_sg:
                self.add_public_security_group_ingress(alb_sg)
            elif self.config.use_nlb():
                self.add_public_security_group_ingress(SG_T)
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
                    ContainerName=self.config.lb_service_name,
                )
            )
        return service_lbs, depends_on

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

    def update_for_service_mesh(self):
        """
        Method to create the AppMesh
        """

    def define_service_ingress(self, settings):
        """
        Function to define microservice ingress.

        :param kwargs: unordered parameters
        :type kwargs: dict
        """
        self.add_service_default_sg()
        service_lbs = Ref(AWS_NO_VALUE)
        registries = self.add_service_to_map()
        if not registries:
            registries = Ref(AWS_NO_VALUE)
        self.service_attrs = {
            "LoadBalancers": service_lbs,
            "ServiceRegistries": registries,
        }
        external_dependencies = []
        if not self.config.ports:
            LOG.debug(
                f"{self.service_name} does not have any ports. No ingress necessary"
            )
            return self.service_attrs, external_dependencies
        if self.config.use_alb() or self.config.use_nlb():
            service_lb = self.add_service_load_balancer(settings)
            self.service_attrs["LoadBalancers"] = service_lb[0]
            self.service_attrs["DependsOn"] = (
                service_lb[-1] if isinstance(service_lb[-1], list) else []
            )

    def generate_service_definition(self, task_definition):
        """
        Function to generate the Service definition.
        This is the last step in defining the service, after all other settings have been prepared.
        """
        service_sgs = [
            Ref(sg) for sg in self.sgs if not isinstance(sg, (Ref, Sub, If, GetAtt))
        ]
        service_sgs += [sg for sg in self.sgs if isinstance(sg, (Ref, Sub, If, GetAtt))]
        if self.config.replicas != ecs_params.SERVICE_COUNT.Default:
            self.parameters[ecs_params.SERVICE_COUNT_T] = self.config.replicas
        self.ecs_service = EcsService(
            ecs_params.SERVICE_T,
            template=self.template,
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
            HealthCheckGracePeriodSeconds=Ref(AWS_NO_VALUE),
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
            TaskDefinition=Ref(task_definition),
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
