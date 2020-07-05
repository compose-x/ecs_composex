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

"""
Main module for AppMesh.

Once all services have been deployed and their VirtualNodes are setup, we deploy the Mesh for it.
"""

from troposphere import AWS_NO_VALUE
from troposphere import Ref, GetAtt, Sub, Parameter
from troposphere import appmesh
from troposphere import ecs
from troposphere.iam import Policy
from troposphere.servicediscovery import (
    DnsConfig as SdDnsConfig,
    Service as SdService,
    DnsRecord as SdDnsRecord,
    Instance as SdInstance,
)

from ecs_composex.appmesh import appmesh_params, appmesh_conditions
from ecs_composex.appmesh.appmesh_conditions import add_appmesh_conditions
from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.common import (
    keyisset,
    build_template,
    add_parameters,
    NONALPHANUM,
    LOG,
)
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_container_config import extend_container_envvars
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_params import VPC_MAP_ID


def initialize_mesh_template():
    """
    Initialize template
    """
    template = build_template(
        "AppMesh Root Template", [MESH_NAME, MESH_OWNER_ID, vpc_params.VPC_DNS_ZONE],
    )
    add_appmesh_conditions(template)
    return template


class Node(object):
    """
    Class representing an AppMesh Node.
    """

    weight = 1

    def __init__(self, service_stack, protocol, backends=None):
        """

        :param ecs_composex.ecs.ServiceStack service_stack: the service template
        """
        self.vnode = None
        self.param_name = service_stack.title
        self.get_param = None
        self.backends = [] if backends is None else backends
        self.stack = service_stack
        self.protocol = protocol
        self.mappings = {}
        self.port_mappings = []
        self.set_port_mappings()
        self.set_listeners_port_mappings()
        self.extend_service_stack()
        self.extend_service_definition()
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
        self.vnode = appmesh.VirtualNode(
            f"{self.stack.title}VirtualNode",
            MeshName=Ref(MESH_NAME),
            MeshOwner=appmesh_conditions.set_mesh_owner_id(),
            VirtualNodeName=GetAtt(sd_service, "Name"),
            Spec=appmesh.VirtualNodeSpec(
                ServiceDiscovery=appmesh.ServiceDiscovery(
                    AWSCloudMap=appmesh.AwsCloudMapServiceDiscovery(
                        NamespaceName=Ref(vpc_params.VPC_MAP_DNS_ZONE),
                        ServiceName=GetAtt(sd_service, "Name"),
                    )
                ),
                Listeners=[
                    appmesh.Listener(PortMapping=port_mapping)
                    for port_mapping in self.port_mappings
                ],
            ),
        )
        self.stack.stack_template.add_resource(self.vnode)
        add_parameters(
            self.stack.stack_template,
            [appmesh_params.MESH_OWNER_ID, appmesh_params.MESH_NAME],
        )
        add_appmesh_conditions(self.stack.stack_template)
        self.stack.stack_template.add_output(
            formatted_outputs(
                [{"VirtualNode": GetAtt(self.vnode, "VirtualNodeName")}],
                export=False,
                obj_name=self.stack.title,
            )
        )

    def set_node_weight(self, weight):
        """
        Method to set the weight of the service

        :param int weight:
        :return:
        """
        self.weight = weight

    def expand_backends(self, root_stack, services):
        """
        Method to set the backends to the service node.

        :param ecs_composex.ecs.ServicesStack root_stack: the root stack to put a dependency from.
        :param dict services: the services in the mesh stack.
        """
        backends = []
        task_def = self.stack.stack_template.resources[ecs_params.TASK_T]
        container_envvars = []
        for backend in self.backends:
            LOG.info(backend)
            virtual_service = services[backend]
            root_stack.stack_template.resources[self.stack.title].DependsOn.append(
                virtual_service.title
            )
            backend_parameter = Parameter(
                f"{backend}VirtualServiceBackend",
                template=self.stack.stack_template,
                Type="String",
            )
            self.stack.Parameters.update(
                {backend_parameter.title: GetAtt(virtual_service, "VirtualServiceName")}
            )
            backends.append(
                appmesh.Backend(
                    VirtualService=appmesh.VirtualServiceBackend(
                        VirtualServiceName=Ref(backend_parameter)
                    )
                )
            )
            container_envvars.append(
                ecs.Environment(
                    Name=f"{backend.upper()}_BACKEND", Value=Ref(backend_parameter)
                )
            )
        for container in task_def.ContainerDefinitions:
            extend_container_envvars(container, env_vars=container_envvars)
        node_spec = getattr(self.vnode, "Spec")
        setattr(node_spec, "Backends", backends)

    def extend_service_definition(self):
        """
        Method to expand the containers configuration and add the Envoy SideCar.
        """
        task = self.stack.service.task
        envoy_port_mapping = []
        # envoy_port_mapping = [
        #     ecs.PortMapping(ContainerPort=port.Port, HostPort=port.Port)
        #     for port in self.port_mappings
        # ]
        envoy_port_mapping.append(ecs.PortMapping(ContainerPort=15000, HostPort=15000))
        envoy_port_mapping.append(ecs.PortMapping(ContainerPort=15001, HostPort=15001))
        envoy_environment = [
            ecs.Environment(
                Name="APPMESH_VIRTUAL_NODE_NAME",
                Value=Sub(
                    f"mesh/${{{MESH_NAME.title}}}/virtualNode/${{{self.vnode.title}.VirtualNodeName}}"
                ),
            ),
            ecs.Environment(
                Name="ENABLE_ENVOY_XRAY_TRACING",
                Value="1" if task.family_config.use_xray else "0",
            ),
            ecs.Environment(Name="ENABLE_ENVOY_STATS_TAGS", Value="1"),
            ecs.Environment(Name="ENVOY_LOG_LEVEL", Value="debug"),
        ]
        envoy_log_config = ecs.LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Ref(ecs_params.LOG_GROUP_T),
                "awslogs-region": Ref("AWS::Region"),
                "awslogs-stream-prefix": "envoy",
            },
        )
        self.stack.stack_template.add_parameter(appmesh_params.ENVOY_IMAGE_URL)
        envoy_container = ecs.ContainerDefinition(
            Image=Ref(appmesh_params.ENVOY_IMAGE_URL),
            Name="envoy",
            Cpu="64",
            Memory="256",
            User="1337",
            Essential=True,
            LogConfiguration=envoy_log_config,
            Environment=envoy_environment,
            PortMappings=envoy_port_mapping,
            Ulimits=[ecs.Ulimit(HardLimit=15000, SoftLimit=15000, Name="nofile")],
            HealthCheck=ecs.HealthCheck(
                Command=[
                    "CMD-SHELL",
                    "curl -s http://localhost:9901/server_info | grep state | grep -q LIVE",
                ],
                Interval=5,
                Timeout=2,
                Retries=3,
            ),
        )
        proxy_config = ecs.ProxyConfiguration(
            ContainerName="envoy",
            Type="APPMESH",
            ProxyConfigurationProperties=[
                ecs.Environment(Name="IgnoredUID", Value="1337"),
                ecs.Environment(Name="ProxyIngressPort", Value="15000",),
                ecs.Environment(Name="ProxyEgressPort", Value="15001"),
                ecs.Environment(Name="IgnoredGID", Value=""),
                ecs.Environment(
                    Name="EgressIgnoredIPs", Value="169.254.170.2,169.254.169.254"
                ),
                ecs.Environment(Name="EgressIgnoredPorts", Value=""),
                ecs.Environment(
                    Name="AppPorts",
                    Value=",".join([f"{port.Port}" for port in self.port_mappings]),
                ),
            ],
        )
        task.containers.append(envoy_container)
        setattr(task.definition, "ProxyConfiguration", proxy_config)
        task.set_task_compute_parameter()

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


class Mesh(object):
    """
    Class for AppMesh mesh
    """

    mesh_title = "AppMesh"
    nodes = "nodes"
    routers = "routers"
    services = "services"
    required_keys = [nodes, routers, services]

    def __init__(
        self, mesh_definition, services_root_stack, services_families, **kwargs
    ):
        """
        Method to initialize the Mesh

        :param ecs_composex.ecs.ServicesStack services_root_stack: The services root stack
        """
        self.nodes = {}
        self.routers = {}
        self.services = {}
        self.routes = []
        self.mesh_settings = mesh_definition["Settings"]
        self.mesh_properties = mesh_definition["Properties"]
        self.stack_parameters = {MESH_NAME.title: self.mesh_properties["MeshName"]}
        self.template = services_root_stack.stack_template
        self.stack = None

        for key in self.required_keys:
            if key not in self.mesh_settings.keys():
                raise KeyError(f"Key {key} is missing. Required {self.required_keys}")

        self.mesh = appmesh.Mesh(
            self.mesh_title,
            Condition=appmesh_conditions.USER_IS_SELF_CON_T,
            MeshName=appmesh_conditions.set_mesh_name(),
            Spec=appmesh.MeshSpec(EgressFilter=appmesh.EgressFilter(Type="DROP_ALL")),
        )
        self.stack_parameters.update(
            {
                appmesh_params.MESH_NAME_T: Ref(appmesh_params.MESH_NAME),
                vpc_params.VPC_DNS_ZONE_T: Ref(vpc_params.VPC_DNS_ZONE),
            }
        )
        nodes_keys = ["name", "protocol", "backends"]
        for node in self.mesh_settings["nodes"]:
            if not set(node.keys()).issubset(nodes_keys):
                raise AttributeError(
                    f"Nodes must have set {nodes_keys}. Got", node.keys()
                )
            if node["name"] not in services_root_stack.stack_template.resources:
                raise AttributeError(
                    f'Node definedd {node["name"]} is not defined in services stack',
                    services_root_stack.stack_template.resources,
                )
            LOG.info(node)
            self.nodes[node["name"]] = Node(
                services_root_stack.stack_template.resources[node["name"]],
                node["protocol"],
                node["backends"] if keyisset("backends", node) else None,
            )
            self.nodes[node["name"]].get_param = GetAtt(
                self.nodes[node["name"]].param_name, f"Outputs.VirtualNode"
            )
            self.nodes[node["name"]].stack.Parameters.update(
                {MESH_NAME.title: appmesh_conditions.get_mesh_name(self.mesh)}
            )
        self.define_routes_and_routers()
        self.define_virtual_services()

    def handle_http_route(self, route_match, nodes, router, http2=False):
        """
        Function to create a HTTP or HTTP/2 route
        :param dict route_match: the route match definition
        :param list<ecs_composex.appmesh.Nodes> nodes: list of nodes
        :param troposphere.appmesh.VirtualRouter router: The virtual router to attach the route to.
        :param http2: whether it is http2
        :return:
        """
        route = appmesh.HttpRoute(
            Match=appmesh.HttpRouteMatch(
                Prefix=route_match["prefix"]
                if keyisset("prefix", route_match)
                else Ref(AWS_NO_VALUE),
                Scheme=route_match["scheme"]
                if keyisset("scheme", route_match)
                else Ref(AWS_NO_VALUE),
                Method=route_match["method"]
                if keyisset("method", route_match)
                else Ref(AWS_NO_VALUE),
            ),
            Action=appmesh.HttpRouteAction(
                WeightedTargets=[
                    appmesh.WeightedTarget(
                        VirtualNode=node.get_param, Weight=node.weight,
                    )
                    for node in nodes
                ]
            ),
        )
        protocol = "HttpRoute"
        if http2:
            protocol = "Http2Route"
        self.routes.append(
            appmesh.Route(
                f"{router.title}{protocol.title()}",
                template=self.template,
                MeshName=appmesh_conditions.get_mesh_name(self.mesh),
                MeshOwner=appmesh_conditions.set_mesh_owner_id(),
                VirtualRouterName=GetAtt(router, "VirtualRouterName"),
                RouteName=Sub(f"${{{router.title}.Uid}}{protocol.title()}"),
                Spec=appmesh.RouteSpec(**{protocol: route}),
            )
        )

    def define_routes_and_routers(self):
        """
        Method to register routers
        :return:
        """
        for router in self.mesh_settings["routers"]:
            name = router["name"]
            router_res_name = NONALPHANUM.sub("", name)
            routes = router["routes"]
            router_listeners = []
            router = appmesh.VirtualRouter(
                f"{router_res_name}VirtualRouter",
                template=self.template,
                MeshName=appmesh_conditions.get_mesh_name(self.mesh),
                MeshOwner=appmesh_conditions.set_mesh_owner_id(),
                VirtualRouterName=Sub(f"{router_res_name}-vr-${{AWS::StackName}}"),
                Spec=appmesh.VirtualRouterSpec(Listeners=router_listeners),
            )
            self.routers[name] = router
            for route_protocol in routes.keys():
                route_nodes = []
                for route in routes[route_protocol]:
                    if not all(key in ["match", "nodes"] for key in route.keys()):
                        raise AttributeError(
                            f"Each route must have match and nodes. Got", route.keys()
                        )
                    for node in route["nodes"]:
                        if node["name"] in self.nodes.keys():
                            route_nodes.append(self.nodes[node["name"]])
                        else:
                            raise ValueError(
                                f'node {node["name"]} is not defined as a virtual node.'
                            )
                    for port_map in route_nodes[0].port_mappings:
                        if port_map.Protocol == route_protocol:
                            setattr(
                                router,
                                "Spec",
                                appmesh.VirtualRouterSpec(
                                    Listeners=[
                                        appmesh.VirtualRouterListener(
                                            PortMapping=route_nodes[0].port_mappings[0]
                                        )
                                    ]
                                ),
                            )
                            break
                    if route_protocol == "http" or route_protocol == "http2":
                        self.handle_http_route(
                            route["match"],
                            route_nodes,
                            router,
                            eval('route_protocol == "http2"'),
                        )

    def define_virtual_services(self):
        """
        Method to parse the services and map them to nodes and routers.
        """
        index = pow(2, 8) - 2
        for service in self.mesh_settings["services"]:
            name = service["name"]
            if keyisset("router", service):
                if not service["router"] in self.routers.keys():
                    raise KeyError(
                        "Routers provided not found in the routers description. Got",
                        service["routers"],
                        "Expected",
                        self.routers.keys(),
                    )
            if keyisset("node", service):
                if not service["node"] in self.nodes.keys():
                    raise KeyError(
                        f"Nodes provided not found in nodes defined. Got",
                        service["node"],
                        "Expected one of",
                        self.nodes.keys(),
                    )
            service_node = (
                self.nodes[service["node"]].get_param
                if keyisset("node", service)
                else None
            )
            service_router = (
                GetAtt(self.routers[service["router"]], "VirtualRouterName")
                if keyisset("router", service)
                else None
            )
            if not service_router and not service_node:
                raise AttributeError(
                    f"The service {name} has neither nodes or routers defined. Define at least one"
                )
            depends = []
            self.services[name] = appmesh.VirtualService(
                NONALPHANUM.sub("", name).title(),
                template=self.template,
                DependsOn=depends,
                MeshName=appmesh_conditions.get_mesh_name(self.mesh),
                MeshOwner=appmesh_conditions.set_mesh_owner_id(),
                VirtualServiceName=Sub(f"{name}.${{{vpc_params.VPC_DNS_ZONE_T}}}"),
                Spec=appmesh.VirtualServiceSpec(
                    Provider=appmesh.VirtualServiceProvider(
                        VirtualNode=appmesh.VirtualNodeServiceProvider(
                            VirtualNodeName=service_node
                        )
                        if service_node
                        else Ref(AWS_NO_VALUE),
                        VirtualRouter=appmesh.VirtualRouterServiceProvider(
                            VirtualRouterName=service_router
                        )
                        if service_router
                        else Ref(AWS_NO_VALUE),
                    )
                ),
            )
            sd_entry = SdService(
                f"{NONALPHANUM.sub('', name).title()}Service",
                template=self.template,
                DependsOn=[self.services[name].title],
                Description=Sub(
                    f"Record for VirtualService {name} in mesh ${{{self.services[name].title}.MeshName}}"
                ),
                NamespaceId=Ref(VPC_MAP_ID),
                DnsConfig=SdDnsConfig(
                    RoutingPolicy="MULTIVALUE",
                    NamespaceId=Ref(AWS_NO_VALUE),
                    DnsRecords=[SdDnsRecord(TTL="30", Type="A")],
                ),
                Name=GetAtt(self.services[name], "VirtualServiceName"),
            )
            SdInstance(
                f"{NONALPHANUM.sub('', name).title()}ServiceFakeInstance",
                template=self.template,
                InstanceAttributes={"AWS_INSTANCE_IPV4": f"169.254.255.{index}"},
                ServiceId=Ref(sd_entry),
            )
            index -= 1

    def render_mesh_template(self, services_stack, **kwargs):
        """
        Method to create the AppMesh template stack.

        :param ecs_composex.ecs.ServicesStack services_stack: The services root stack
        """
        if self.mesh.title not in services_stack.stack_template.resources:
            services_stack.stack_template.add_resource(self.mesh)
            add_appmesh_conditions(services_stack.stack_template)
            add_parameters(
                services_stack.stack_template,
                [
                    appmesh_params.MESH_OWNER_ID,
                    appmesh_params.MESH_NAME,
                    vpc_params.VPC_DNS_ZONE,
                ],
            )
            services_stack.Parameters.update(
                {
                    vpc_params.VPC_DNS_ZONE_T: GetAtt(
                        "vpc", f"Outputs.{vpc_params.VPC_MAP_DNS_ZONE_T}"
                    )
                }
            )
        for res_name in services_stack.stack_template.resources:
            res = services_stack.stack_template.resources[res_name]
            if issubclass(type(res), ComposeXStack):
                res.DependsOn.append(self.mesh.title)
        for node_name in self.nodes:
            if self.nodes[node_name].backends:
                self.nodes[node_name].expand_backends(services_stack, self.services)
