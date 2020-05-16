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
from troposphere import Ref, Sub, GetAtt, ImportValue
from troposphere.ec2 import EIP, SecurityGroup
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import LoadBalancer as EcsLoadBalancer
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
)

from ecs_composex.common import keyisset, LOG
from ecs_composex.common import add_parameters
from ecs_composex.common import build_template, NONALPHANUM
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.config import ComposeXConfig
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.ecs import ecs_params, ecs_conditions
from ecs_composex.ecs.ecs_conditions import USE_HOSTNAME_CON_T
from ecs_composex.ecs.ecs_iam import add_service_roles
from ecs_composex.ecs.ecs_params import NETWORK_MODE, EXEC_ROLE_T, TASK_ROLE_T, TASK_T
from ecs_composex.ecs.ecs_params import SERVICE_NAME, SERVICE_HOSTNAME
from ecs_composex.ecs.ecs_params import (
    SERVICE_NAME_T,
    SG_T,
)
from ecs_composex.vpc import vpc_params, vpc_conditions
from ecs_composex.vpc.vpc_conditions import USE_VPC_MAP_ID_CON_T
from ecs_composex.vpc.vpc_params import VPC_ID, PUBLIC_SUBNETS
from ecs_composex.vpc.vpc_params import VPC_MAP_ID
from ecs_composex.ecs.ecs_xray import define_xray_container

CIDR_REG = r"""((((((([0-9]{1}\.))|([0-9]{2}\.)|
(1[0-9]{2}\.)|(2[0-5]{2}\.)))){3})(((((([0-9]{1}))|
([0-9]{2})|(1[0-9]{2})|(2[0-5]{2}))))){1,3})\/(([0-9])|([1-2][0-9])|((3[0-2])))$"""
CIDR_PAT = re.compile(CIDR_REG)

STATIC = 0


def flatten_ip(ip_str):
    """Function to remove all non alphanum characters from IP CIDR notation

    :param ip_str:

    :rtype: str
    """
    return ip_str.replace(".", "").split("/")[0].strip()


def extend_env_vars(container, env_vars):
    if (
        isinstance(container, ContainerDefinition)
        and not isinstance(container.Name, (Ref, Sub, GetAtt, ImportValue))
        and container.Name.startswith("AWS")
    ):
        LOG.debug(f"Ignoring AWS Container {container.Name}")
        return
    environment = (
        getattr(container, "Environment")
        if hasattr(container, "Environment")
        and not isinstance(getattr(container, "Environment"), Ref)
        else []
    )
    if environment:
        environment += env_vars
    else:
        setattr(container, "Environment", env_vars)
    LOG.debug(environment)


def import_env_variables(environment):
    """
    Function to import Docker compose env variables into ECS Env Variables

    :param environment: Environment variables as defined on the ecs_service definition
    :type environment: dict
    :return: list of Environment
    :rtype: list<troposphere.ecs.Environment>
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

    :param ports: list of ports used by the ecs_service
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
    Function to generate placement strategies. Defaults to spreading across all AZs

    :return: list of placement strategies
    :rtype: list
    """
    return [
        PlacementStrategy(Field="instanceId", Type="spread"),
        PlacementStrategy(Field="attribute:ecs.availability-zone", Type="spread"),
    ]


def define_protocol(port_string):
    """
    Function to define the port protocol. Defaults to TCP if not specified otherwise

    :param port_string: the port string to parse from the ports list in the compose file
    :type port_string: str
    :return: protocol, ie. udp or tcp
    :rtype: str
    """
    protocols = ["tcp", "udp"]
    protocol = "tcp"
    if port_string.find("/"):
        protocol_found = port_string.split("/")[-1].strip()
        if protocol_found in protocols:
            return protocol_found
    return protocol


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


def initialize_service_template(service_name):
    """Function to initialize the base template for ECS Services with all
    parameters and conditions necessary for CFN to work properly

    :param service_name: Name of the ecs_service as defined in ComposeX File
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
    Class specifically dealing with the configuration and settings of the ecs_service from how it was defined in
    the compose file

    :cvar list keys: List of valid settings for a service in Docker compose syntax reference
    :cvar list service_config_keys: list of extra configuration that apply to services.
    :cvar bool use_cloudmap: Indicates whether or not the service will be added to the VPC CloudMap
    :cvar bool use_alb: Indicates to use an AWS Application LoadBalancer (ELBv2, type application)
    :cvar bool use_nlb: Indicates to use an AWS Application LoadBalancer (ELBv2, type network)
    :cvar bool is_public: Indicates whether the service should be accessible publicly
    :cvar str boundary: IAM boundary policy to use for the IAM Roles (Execution and Task)
    :cvar str lb_type: Indicates the type of ELBv2 to use (application or network)
    :cvar str hostname: the hostname to use to route to the service.
    :cvar str command: the command to use for the service start
    :cvar list ports: List of ports to use for the microservice.
    :cvar list links: list of links as indicated in the compose file, indicating connection dependencies.
    :cvar bool use_xray: Indicates whether or not add the X-Ray Daemon to the task definition.
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
    service_config_keys = ["xray"]
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
    use_xray = False

    def set_xray(self, config):
        """
        Function to set the xray
        """
        if keyisset("enabled", config):
            self.use_xray = config["enabled"]

    def define_service_ports(self, ports):
        """Function to define common structure to ports

        :return: list of ports the ecs_service uses formatted according to dict
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
                "Both ALB and NLB are enabled for this ecs_service. Defaulting to ALB"
            )
            self.use_nlb = False
        elif self.use_nlb and not self.use_alb:
            self.lb_type = "network"
        LOG.debug(f"Setting LB type to {self.lb_type}")

    def __init__(self, content, service_name, definition):
        """
        Function to initialize the ecs_service configuration
        :param content:
        """
        configs = {}
        if keyisset("configs", definition):
            configs = definition["configs"]
        for key in self.service_config_keys:
            if key not in self.valid_config_keys:
                self.valid_config_keys.append(key)
        super().__init__(content, service_name, configs)
        if not set(self.required_keys).issubset(set(definition)):
            raise AttributeError(
                "Required attributes for a ecs_service are", self.required_keys
            )
        self.image = definition["image"]
        self.command = (
            definition["command"].strip() if keyisset("command", definition) else None
        )
        self.entrypoint = (
            definition["entrypoint"] if keyisset("entrypoint", definition) else None
        )
        self.sort_load_balancing()
        if keyisset("ports", definition):
            self.define_service_ports(definition["ports"])
        self.environment = (
            definition["environment"] if keyisset("environment", definition) else []
        )
        if keyisset("hostname", definition):
            self.hostname = definition["hostname"]


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

    links = []
    dependencies = []
    network_settings = None
    config = None
    task_definition = None
    ecs_service = None
    eips = []
    service_attrs = None

    def add_service_default_sg(self):
        """
        Adds a default security group for the microservice.
        """
        self.template.add_resource(
            SecurityGroup(
                SG_T,
                GroupDescription=Sub(
                    f"SG for ${{{SERVICE_NAME_T}}} - ${{{ROOT_STACK_NAME_T}}}"
                ),
                Tags=Tags(
                    {
                        "Name": Sub(f"${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"),
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
            "EcsDiscoveryService",
            template=self.template,
            Condition=USE_VPC_MAP_ID_CON_T,
            Description=f"{self.service_name}",
            NamespaceId=Ref(VPC_MAP_ID),
            HealthCheckCustomConfig=SdHealthCheckCustomConfig(FailureThreshold=1.0),
            DnsConfig=SdDnsConfig(
                RoutingPolicy="MULTIVALUE",
                NamespaceId=Ref(AWS_NO_VALUE),
                DnsRecords=[
                    SdDnsRecord(TTL="30", Type="A"),
                    SdDnsRecord(TTL="30", Type="SRV"),
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
                    title = f"From{allowed_source['source_name'].title()}Onto{port['target']}{port['protocol']}"
                    description = Sub(
                        f"From {allowed_source['source_name'].title()} "
                        f"To {port['target']}{port['protocol']} for ${{{SERVICE_NAME_T}}}"
                    )
                else:
                    title = (
                        f"From{flatten_ip(allowed_source['ipv4'])}"
                        "To{port['target']}{port['protocol']}"
                    )
                    description = Sub(
                        f"Public {port['target']}{port['protocol']}"
                        f" for ${{{SERVICE_NAME_T}}}"
                    )
                SecurityGroupIngress(
                    title,
                    template=self.template,
                    Description=description,
                    GroupId=GetAtt(security_group, "GroupId"),
                    IpProtocol=port["protocol"],
                    FromPort=port["target"],
                    ToPort=port["target"],
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

    def add_lb_listener(self, port, lb, tgt):
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
            f"{self.config.lb_type.title()}{suffix}ListenerPort{port}",
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

    def add_load_balancer(self, ports, **kwargs):
        """Function to add LB to template

        :return: loadbalancer
        :rtype: troposphere.elasticloadbalancingv2.LoadBalancer
        """
        alb_sg = None
        if self.config.is_public and self.config.lb_type == "network":
            self.add_public_ips(kwargs["AwsAzs"])

        no_value = Ref(AWS_NO_VALUE)
        public_mapping = define_public_mapping(self.eips, kwargs["AwsAzs"])
        if ports and self.config.lb_type == "application":
            alb_sg = self.add_alb_sg(ports)
            self.add_lb_to_service_ingress(alb_sg, SG_T)
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
            if self.config.is_public and self.config.lb_type == "network"
            else no_value,
            Subnets=Ref(PUBLIC_SUBNETS)
            if self.config.is_public and self.config.lb_type == "application"
            else no_value,
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
            if self.config.lb_type == "application" and alb_sg:
                self.add_public_security_group_ingress(alb_sg)
            elif self.config.lb_type == "network":
                self.add_public_security_group_ingress(SG_T)
        return loadbalancer

    def add_service_load_balancer(self, **kwargs):
        """Function to add all ELBv2 resources for a microservice

        :return: service_lbs, depends_on
        :rtype: tuple
        """
        service_lbs = []
        tgt_groups = []
        depends_on = []
        curated_ports = [int(port["target"]) for port in self.config.ports]
        service_lb = self.add_load_balancer(curated_ports, **kwargs)
        depends_on.append(service_lb.title)
        for port in curated_ports:
            tgt = self.add_target_group(port, service_lb)
            listener = self.add_lb_listener(port, service_lb, tgt)
            tgt_groups.append(tgt)
            depends_on.append(tgt.title)
            depends_on.append(listener.title)

        for target in tgt_groups:
            service_lbs.append(
                EcsLoadBalancer(
                    TargetGroupArn=Ref(target),
                    ContainerPort=tgt.Port,
                    ContainerName=Ref(SERVICE_NAME),
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

    def define_container_definition(self):
        """
        Generates the container definition
        """
        env_vars = import_env_variables(self.config.environment)
        mappings = generate_port_mappings(self.config.ports)
        if not mappings:
            mappings = Ref(AWS_NO_VALUE)
        container = ContainerDefinition(
            # EntryPoint=If(ENTRY_CON, Ref('AWS::NoValue'), Split(' ', Ref(params.SERVICE_ENTRYPOINT))),
            Command=self.config.command.strip().split(";")
            if self.config.command
            else Ref(AWS_NO_VALUE),
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
            Environment=env_vars if env_vars else Ref(AWS_NO_VALUE),
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
        to the ecs_service template
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
        containers = [self.define_container_definition()]
        if self.config.use_xray:
            containers.append(define_xray_container())
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
            ContainerDefinitions=containers,
            RequiresCompatibilities=["EC2", "FARGATE"],
            Tags=Tags(
                {
                    "Name": Ref(ecs_params.SERVICE_NAME),
                    "Environment": Ref(AWS_STACK_NAME),
                }
            ),
        )

    def define_service_network_config(self, **kwargs):
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
        if not keyisset("AwsAzs", kwargs):
            raise KeyError(
                "Missing AwsAzs from options."
                "AZs are required to configure services networking"
            )
        if not self.config.ports:
            LOG.debug(
                f"{self.service_name} does not have any ports. No ingress necessary"
            )
            return self.service_attrs, external_dependencies
        if self.config.use_alb or self.config.use_nlb:
            service_lb = self.add_service_load_balancer(**kwargs)
            self.service_attrs["LoadBalancers"] = service_lb[0]
            self.service_attrs["DependsOn"] = (
                service_lb[-1] if isinstance(service_lb[-1], list) else []
            )

    def generate_service_definition(self):
        """
        Function to generate the Service definition.
        This is the last step in defining the service, after all other settings have been prepared.
        """
        service_sgs = [Ref(sg) for sg in self.sgs]
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
            TaskDefinition=Ref(ecs_params.TASK_T),
            LaunchType=Ref(ecs_params.LAUNCH_TYPE),
            Tags=Tags(
                {
                    "Name": Ref(ecs_params.SERVICE_NAME),
                    "StackName": Ref(AWS_STACK_NAME),
                }
            ),
            PropagateTags="SERVICE",
            **self.service_attrs,
        )

    def __init__(self, service_name, definition, content, **kwargs):
        """
        Function to initialize the Service object
        :param service_name: Name of the service
        :type service_name: str
        :param definition: the service definition as defined in compose file
        :type definition: dict
        :param content: the docker compose content, in full
        :type content: dict
        :param kwargs: unordered arguments
        :type kwargs: dict
        """
        self.definition = definition
        self.config = ServiceConfig(content, service_name, definition)
        LOG.debug(self.config)
        self.links = definition["links"] if keyisset("links", definition) else []
        self.dependencies = (
            definition["depends_on"] if keyisset("depends_on", definition) else []
        )
        self.service_name = service_name
        if not keyisset("image", definition):
            raise KeyError(f"No image property set for ecs_service {service_name}")
        self.environment = (
            definition["environment"] if keyisset("environment", definition) else []
        )
        self.resource_name = NONALPHANUM.sub("", self.service_name)
        self.hostname = (
            self.config.hostname if self.config.hostname else self.resource_name
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
        self.add_task_defnition()
        self.sgs = [ecs_params.SG_T, ecs_params.CLUSTER_SG_ID]
        self.define_service_network_config(**kwargs)
        self.generate_service_definition()
        self.generate_service_template_outputs()
