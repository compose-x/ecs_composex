#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

from troposphere import Parameter
from troposphere import Ref, Sub, GetAtt
from troposphere import appmesh
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import (
    Environment,
    PortMapping,
    LogConfiguration,
    ContainerDefinition,
    Ulimit,
    ProxyConfiguration,
    HealthCheck,
)
from troposphere.iam import Policy

from ecs_composex.appmesh import appmesh_params, appmesh_conditions, metadata
from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.dns.dns_params import PRIVATE_DNS_ZONE_NAME
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_container_config import extend_container_envvars


class MeshNode(object):
    """
    Class representing an AppMesh Node.
    """

    weight = 1

    def __init__(self, service_stack, protocol, backends=None):
        """

        :param ecs_composex.ServiceStack service_stack: the service template
        """
        self.node = None
        self.param_name = service_stack.title
        self.get_node_param = None
        self.get_sg_param = None
        self.backends = [] if backends is None else backends
        self.stack = service_stack
        self.protocol = protocol
        self.mappings = {}
        self.port_mappings = []
        self.set_port_mappings()
        self.set_listeners_port_mappings()
        self.extend_service_stack()
        self.add_envoy_container_definition()
        self.extend_task_policy()

    def set_port_mappings(self):
        """
        Method to set the port mappings based on the service config ports
        """
        target = "target"
        published = "published"
        for port in self.stack.config.ports:
            if port[target] not in self.mappings.keys():
                self.mappings[port[target]] = {port[published]: port}
            elif (
                port[target] in self.mappings.keys()
                and not port[published] in self.mappings[port[target]]
            ):
                self.mappings[port[target]][port[published]] = port

    def set_listeners_port_mappings(self):
        """
        Method to set the listeners port_mappings
        """
        self.port_mappings = [
            appmesh.PortMapping(Port=port["published"], Protocol=self.protocol)
            for port in self.stack.config.ports
        ]

    def extend_service_stack(self):
        """
        Method to expand the service template with the AppMesh virtual node
        """
        sd_service_name = f"{self.stack.title}DiscoveryService"
        sd_service = self.stack.stack_template.resources[sd_service_name]
        self.node = appmesh.VirtualNode(
            f"{self.stack.title}VirtualNode",
            MeshName=Ref(appmesh_params.MESH_NAME),
            MeshOwner=Ref(appmesh_params.MESH_OWNER_ID),
            VirtualNodeName=GetAtt(sd_service, "Name"),
            Spec=appmesh.VirtualNodeSpec(
                ServiceDiscovery=appmesh.ServiceDiscovery(
                    AWSCloudMap=appmesh.AwsCloudMapServiceDiscovery(
                        NamespaceName=Ref(PRIVATE_DNS_ZONE_NAME),
                        ServiceName=GetAtt(sd_service, "Name"),
                    )
                ),
                Listeners=[
                    appmesh.Listener(PortMapping=port_mapping)
                    for port_mapping in self.port_mappings
                ],
            ),
            Metadata=metadata,
        )
        self.stack.stack_template.add_resource(self.node)
        add_parameters(
            self.stack.stack_template,
            [appmesh_params.MESH_OWNER_ID, appmesh_params.MESH_NAME],
        )
        self.stack.Parameters.update(
            {
                appmesh_params.MESH_NAME.title: Ref(appmesh_params.MESH_NAME),
                appmesh_params.MESH_OWNER_ID.title: Ref(appmesh_params.MESH_OWNER_ID),
            }
        )
        appmesh_conditions.add_appmesh_conditions(self.stack.stack_template)
        self.stack.stack_template.add_output(
            ComposeXOutput(
                self.node,
                [("VirtualNode", "", GetAtt(self.node, "VirtualNodeName"))],
                duplicate_attr=True,
                export=False,
            ).outputs
        )

    def set_node_weight(self, weight):
        """
        Method to set the weight of the service

        :param int weight:
        :return:
        """
        self.weight = weight

    def add_envoy_container_definition(self):
        """
        Method to expand the containers configuration and add the Envoy SideCar.
        """
        envoy_container_name = "envoy"
        task = self.stack.service.task
        envoy_port_mapping = [
            PortMapping(ContainerPort=15000, HostPort=15000),
            PortMapping(ContainerPort=15001, HostPort=15001),
        ]
        envoy_environment = [
            Environment(
                Name="APPMESH_VIRTUAL_NODE_NAME",
                Value=Sub(
                    f"mesh/${{{appmesh_params.MESH_NAME.title}}}/virtualNode/${{{self.node.title}.VirtualNodeName}}"
                ),
            ),
            Environment(
                Name="ENABLE_ENVOY_XRAY_TRACING",
                Value="1" if task.family_config.use_xray else "0",
            ),
            Environment(Name="ENABLE_ENVOY_STATS_TAGS", Value="1"),
        ]
        envoy_log_config = LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Ref(ecs_params.LOG_GROUP_T),
                "awslogs-region": Ref("AWS::Region"),
                "awslogs-stream-prefix": envoy_container_name,
            },
        )
        self.stack.stack_template.add_parameter(appmesh_params.ENVOY_IMAGE_URL)
        envoy_container = ContainerDefinition(
            Image=Ref(appmesh_params.ENVOY_IMAGE_URL),
            Name=envoy_container_name,
            Cpu=128,
            Memory=256,
            User="1337",
            Essential=True,
            LogConfiguration=envoy_log_config,
            Environment=envoy_environment,
            PortMappings=envoy_port_mapping,
            Ulimits=[Ulimit(HardLimit=15000, SoftLimit=15000, Name="nofile")],
            HealthCheck=HealthCheck(
                Command=[
                    "CMD-SHELL",
                    "curl -s http://localhost:9901/server_info | grep state | grep -q LIVE",
                ],
                Interval=5,
                Timeout=2,
                Retries=3,
                StartPeriod=10,
            ),
        )
        proxy_config = ProxyConfiguration(
            ContainerName="envoy",
            Type="APPMESH",
            ProxyConfigurationProperties=[
                Environment(Name="IgnoredUID", Value="1337"),
                Environment(
                    Name="ProxyIngressPort",
                    Value="15000",
                ),
                Environment(Name="ProxyEgressPort", Value="15001"),
                Environment(Name="IgnoredGID", Value=""),
                Environment(
                    Name="EgressIgnoredIPs", Value="169.254.170.2,169.254.169.254"
                ),
                Environment(Name="EgressIgnoredPorts", Value=""),
                Environment(
                    Name="AppPorts",
                    Value=",".join([f"{port.Port}" for port in self.port_mappings]),
                ),
            ],
        )
        task.containers.append(envoy_container)
        setattr(task.definition, "ProxyConfiguration", proxy_config)
        task.set_task_compute_parameter()
        self.stack.Parameters.update(task.stack_parameters)

    def extend_task_policy(self):
        """
        Method to add a policy for AppMesh Access
        """
        policy = Policy(
            PolicyName="AppMeshAccess",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AppMeshAccess",
                        "Effect": "Allow",
                        "Action": ["appmesh:StreamAggregatedResources"],
                        "Resource": ["*"],
                    },
                    {
                        "Sid": "ServiceDiscoveryAccess",
                        "Effect": "Allow",
                        "Action": [
                            "servicediscovery:Get*",
                            "servicediscovery:Describe*",
                            "servicediscovery:List*",
                            "servicediscovery:DiscoverInstances*",
                        ],
                        "Resource": "*",
                    },
                ],
            },
        )
        task_role = self.stack.stack_template.resources[ecs_params.TASK_ROLE_T]
        if hasattr(task_role, "Policies") and isinstance(
            getattr(task_role, "Policies"), list
        ):
            policies = getattr(task_role, "Policies")
            policies.append(policy)
        elif not hasattr(task_role, "Policies"):
            setattr(task_role, "Policies", [policy])

    def expand_backends(self, root_stack, services):
        """
        Method to set the backends to the service node.

        :param ecs_composex.ServicesStack root_stack: the root stack to put a dependency from.
        :param dict services: the services in the mesh stack.
        """
        backends = []
        task_def = self.stack.stack_template.resources[ecs_params.TASK_T]
        container_envvars = []
        for backend in self.backends:
            LOG.debug(backend)
            virtual_service = services[backend]
            backends_nodes = virtual_service.get_backend_nodes()
            LOG.debug(backends_nodes)
            self.create_ingress_rule(root_stack, backends_nodes)
            root_stack.stack_template.resources[self.stack.title].DependsOn.append(
                virtual_service.service.title
            )
            backend_parameter = Parameter(
                f"{backend}VirtualServiceBackend",
                template=self.stack.stack_template,
                Type="String",
            )
            self.stack.Parameters.update(
                {
                    backend_parameter.title: GetAtt(
                        virtual_service.service, "VirtualServiceName"
                    )
                }
            )
            backends.append(
                appmesh.Backend(
                    VirtualService=appmesh.VirtualServiceBackend(
                        VirtualServiceName=Ref(backend_parameter)
                    )
                )
            )
            container_envvars.append(
                Environment(
                    Name=f"{backend.upper()}_BACKEND", Value=Ref(backend_parameter)
                )
            )
        for container in task_def.ContainerDefinitions:
            extend_container_envvars(container, env_vars=container_envvars)
        node_spec = getattr(self.node, "Spec")
        setattr(node_spec, "Backends", backends)

    def create_ingress_rule(self, root_stack, nodes):
        """
        Creates EC2 ingress rules to allow all traffic from node to backends nodes SG.

        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        :param list<ecs_composex.appmesh.appmesh_nodes.MeshNodes> nodes: list of nodes
        """
        for node in nodes:
            rule_name = f"AllowAllFrom{self.node.title}To{node.node.title}ForMesh"
            LOG.debug(rule_name)
            SecurityGroupIngress(
                rule_name,
                template=root_stack.stack_template,
                FromPort="-1",
                ToPort="-1",
                GroupId=node.get_sg_param,
                SourceSecurityGroupId=self.get_sg_param,
                IpProtocol="-1",
            )
