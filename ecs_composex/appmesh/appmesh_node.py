# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .appmesh_mesh import Mesh
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import GetAtt, Output, Parameter, Ref, Sub, appmesh
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import Environment, ProxyConfiguration

from ecs_composex.appmesh import appmesh_conditions, appmesh_params, metadata
from ecs_composex.appmesh.appmesh_conditions import get_mesh_name, get_mesh_owner
from ecs_composex.appmesh.appmesh_params import BACKENDS_KEY
from ecs_composex.cloudmap.cloudmap_params import ECS_SERVICE_NAMESPACE_SERVICE_NAME
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
    add_update_mapping,
)
from ecs_composex.compose.compose_services.helpers import extend_container_envvars
from ecs_composex.ecs.managed_sidecars import ManagedSidecar


class MeshNode:
    """
    Class representing an AppMesh Node.
    """

    weight = 1

    def __init__(
        self,
        family: ComposeFamily,
        protocol: str,
        port: int,
        mesh: Mesh,
        settings: ComposeXSettings,
        backends: list = None,
    ):
        """
        Creates the AppMesh VirtualNode pointing to the family service
        """
        self.node = None
        self.param_name = family.logical_name
        self.get_node_param = None
        self.get_sg_param = None
        self.backends = [] if backends is None else backends
        self.stack = mesh.stack
        self.template = mesh.stack.stack_template
        self.service_config = family.service_networking
        self.protocol = protocol.lower()
        self.port = int(port)
        self.mappings = {}
        self.service = None
        self.port_mappings = [
            appmesh.PortMapping(Port=self.port, Protocol=self.protocol)
        ]
        self.create_service_virtual_node(family, mesh, settings)
        self.add_envoy_container_definition(mesh, family)

    def create_service_virtual_node(
        self, family: ComposeFamily, mesh: Mesh, settings: ComposeXSettings
    ):
        """
        Method to expand the service template with the AppMesh virtual node
        """
        service_node_name = family.service_networking.sd_service.set_update_attribute(
            ECS_SERVICE_NAMESPACE_SERVICE_NAME, self.stack
        )
        namespace = family.service_networking.sd_service.namespace
        if namespace.cfn_resource:
            add_parameters(
                self.stack.stack_template, [namespace.zone_dns_name["ImportParameter"]]
            )
            self.stack.Parameters.update(
                {
                    namespace.zone_dns_name[
                        "ImportParameter"
                    ].title: namespace.zone_dns_name["ImportValue"]
                }
            )
            namespace_name = Ref(namespace.zone_dns_name["ImportParameter"])
        elif namespace.mappings:
            add_update_mapping(
                self.stack.stack_template,
                namespace.module.mapping_key,
                settings.mappings[namespace.module.mapping_key],
            )
            namespace_name = namespace.zone_dns_name["ImportValue"]
        else:
            raise KeyError()

        self.node = appmesh.VirtualNode(
            f"{family.logical_name}VirtualNode",
            MeshName=get_mesh_name(mesh.appmesh),
            MeshOwner=get_mesh_owner(mesh.appmesh),
            VirtualNodeName=Sub(
                f"{family.logical_name}${{STACK_NAME}}",
                STACK_NAME=define_stack_name(self.stack.stack_template),
            ),
            Spec=appmesh.VirtualNodeSpec(
                ServiceDiscovery=appmesh.ServiceDiscovery(
                    AWSCloudMap=appmesh.AwsCloudMapServiceDiscovery(
                        NamespaceName=namespace_name, ServiceName=service_node_name
                    )
                ),
                Listeners=[
                    appmesh.Listener(PortMapping=mapping)
                    for mapping in self.port_mappings
                ],
            ),
            Metadata=metadata,
        )
        add_resource(self.stack.stack_template, self.node)
        appmesh_conditions.add_appmesh_conditions(self.stack.stack_template)
        # todo: add output to stack for the node

    def set_node_weight(self, weight):
        """
        Method to set the weight of the service

        :param int weight:
        :return:
        """
        self.weight = weight

    def add_envoy_container_definition(self, mesh: Mesh, family: ComposeFamily):
        """
        Method to expand the containers configuration and add the Envoy SideCar.
        """
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
                    Name="EgressIgnoredIPs",
                    Value="169.254.170.2,169.254.169.254",
                ),
                Environment(Name="EgressIgnoredPorts", Value=""),
                Environment(
                    Name="AppPorts",
                    Value=",".join([f"{port.Port}" for port in self.port_mappings]),
                ),
            ],
        )

        envoy_service = ManagedSidecar(
            "envoy",
            {
                "image": "public.ecr.aws/appmesh/aws-appmesh-envoy:v1.22.0.0-prod",
                "user": "1337",
                "deploy": {"resources": {"limits": {"cpus": 0.125, "memory": "256MB"}}},
                "environment": {
                    "ENABLE_ENVOY_XRAY_TRACING": 0 if not family.want_xray else 1,
                },
                "ports": [
                    {"target": 15000, "published": 15000, "protocol": "tcp"},
                    {"target": 15001, "published": 15001, "protocol": "tcp"},
                ],
                "expose": ["9901/tcp"],
                "healthcheck": {
                    "test": [
                        "CMD-SHELL",
                        "curl -s http://localhost:9901/server_info | grep state | grep -q LIVE",
                    ],
                    "interval": "5s",
                    "timeout": "2s",
                    "retries": 3,
                    "start_period": "10s",
                },
                "labels": {"container_name": "envoy", "usage": "appmesh"},
                "ulimits": {"nofile": {"soft": 15000, "hard": 15000}},
                "x-iam": {
                    "Policies": [
                        {
                            "PolicyName": "AppMeshAccess",
                            "PolicyDocument": {
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
                        }
                    ]
                },
            },
            is_essential=True,
        )
        virtual_node_parameter = Parameter(self.node.title, Type="String")
        add_parameters(
            family.template, [virtual_node_parameter, appmesh_params.MESH_NAME]
        )
        family.stack.Parameters.update(
            {
                virtual_node_parameter.title: GetAtt(
                    self.stack.title, f"Outputs.{self.node.title}"
                ),
                appmesh_params.MESH_NAME.title: GetAtt(
                    mesh.stack.title,
                    f"Outputs.{appmesh_params.MESH_NAME.title}",
                ),
            }
        )
        add_outputs(
            self.stack.stack_template,
            [Output(self.node.title, Value=GetAtt(self.node, "VirtualNodeName"))],
        )
        envoy_service.container_definition.Environment.append(
            Environment(
                Name="APPMESH_VIRTUAL_NODE_NAME",
                Value=Sub(
                    f"mesh/${{{appmesh_params.MESH_NAME.title}}}/virtualNode/${{{virtual_node_parameter.title}}}"
                ),
            )
        )
        envoy_service.add_to_family(family, is_dependency=True)
        setattr(family.task_definition, "ProxyConfiguration", proxy_config)
        self.service = envoy_service

    def expand_backends(self, mesh: Mesh, root_stack, services):
        """
        Method to set the backends to the service node.

        :param ecs_composex.ServicesStack root_stack: the root stack to put a dependency from.
        :param dict services: the services in the mesh stack.
        """
        backends = []
        task_def = self.service.family.task_definition
        container_envvars = []
        backend_service_outputs: list[Output] = []
        for backend in self.backends:
            LOG.debug(backend)
            virtual_service = services[backend]
            backends_nodes = virtual_service.get_backend_nodes()
            LOG.debug(backends_nodes)
            self.create_ingress_rule(root_stack, backends_nodes)
            backend_parameter = Parameter(
                f"{backend}VirtualServiceBackend",
                template=self.service.family.template,
                Type="String",
            )
            backend_service_output = Output(
                f"{backend_parameter.title}VirtualServiceName",
                Value=GetAtt(virtual_service.service, "VirtualServiceName"),
            )
            backend_service_outputs.append(backend_service_output)

            self.service.family.stack.Parameters.update(
                {
                    backend_parameter.title: GetAtt(
                        "appmesh", f"Outputs.{backend_service_output.title}"
                    )
                }
            )
            backends.append(
                appmesh.Backend(
                    VirtualService=appmesh.VirtualServiceBackend(
                        VirtualServiceName=GetAtt(
                            virtual_service.service, "VirtualServiceName"
                        )
                    )
                )
            )
            container_envvars.append(
                Environment(
                    Name=f"{backend.upper()}_BACKEND",
                    Value=Ref(backend_parameter),
                )
            )
        add_outputs(mesh.stack.stack_template, backend_service_outputs)
        for container in task_def.ContainerDefinitions:
            extend_container_envvars(container, env_vars=container_envvars)
        node_spec = getattr(self.node, "Spec")
        setattr(node_spec, BACKENDS_KEY, backends)

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
