# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Package to manage an ECS "Family" Task and Service definition
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

import re
from itertools import chain

from troposphere import AWS_STACK_NAME, GetAtt, If, Join, NoValue
from troposphere import Output as CfnOutput
from troposphere import Ref, Region, Tags
from troposphere.ecs import EphemeralStorage, RuntimePlatform, TaskDefinition

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.compose_services import ComposeService
from ecs_composex.ecs import ecs_conditions, ecs_params
from ecs_composex.ecs.ecs_family.family_helpers import (
    handle_same_task_services_dependencies,
)
from ecs_composex.ecs.ecs_family.family_logging import FamilyLogging
from ecs_composex.ecs.ecs_params import TASK_T
from ecs_composex.ecs.ecs_prometheus import set_prometheus
from ecs_composex.ecs.managed_sidecars.aws_xray import set_xray
from ecs_composex.ecs.service_compute import ServiceCompute
from ecs_composex.ecs.service_networking import ServiceNetworking
from ecs_composex.ecs.service_networking.helpers import update_family_subnets
from ecs_composex.ecs.service_scaling import ServiceScaling
from ecs_composex.ecs.task_compute import TaskCompute
from ecs_composex.ecs.task_iam import TaskIam

from ...common.troposphere_tools import add_outputs, add_parameters
from .family_helpers import assign_secrets_to_roles, ensure_essential_containers
from .family_template import set_template
from .task_runtime import define_family_runtime_parameters


class ComposeFamily:
    """
    Class to group services logically to create the final ECS Task and Service definitions

    Processing order

    * Import first service
    * Define LaunchType
    * Define CapacityProviders if set
        This helps determine if we run in EXTERNAL mode early, as a lot of networking settings won't apply.

    :ivar list[ecs_composex.compose.compose_services.ComposeService] services: List of the Services part of the family
    :ivar ecs_composex.ecs.ecs_service.Service ecs_service: ECS Service settings
    :ivar ecs_composex.ecs.task_iam.TaskIam iam_manager:
    :ivar TaskCompute task_compute: Task Compute manager
    """

    def __init__(self, services, family_name):
        self._compose_services = services
        self.ordered_services = services
        self.managed_sidecars = []
        self.name = family_name
        self.logical_name = re.sub(r"[^a-zA-Z0-9]+", "", family_name)
        self.family_hostname = self.name.replace("_", "-").lower()
        self.services_depends_on = []
        self.template = set_template(self)
        self.stack: ServiceStack = ServiceStack(
            self.logical_name,
            stack_template=self.template,
        )
        self.logging = None
        self.umbrella_log_group = None
        self.firelens_service = None
        self.firelens_config_service = None
        self.cwagent_service = None
        self.xray_service = None
        self.task_definition = None
        self.service_definition = None
        self.service_tags = None
        self.task_ephemeral_storage = 0
        self.enable_execute_command = False
        self.ecs_service = None
        self.runtime_cpu_arch = None
        self.runtime_os_family = None
        self.outputs = []
        self.task_logging_options = {}
        self.alarms = {}
        self.predefined_alarms = {}
        self.target_groups = []
        self.iam_manager = TaskIam(self)
        self.iam_manager.init_update_policies()
        self.service_scaling = None
        self.service_networking = None
        self.task_compute = None
        self.service_compute = ServiceCompute(self)

    @property
    def services(self) -> list:
        return list(chain(self.managed_sidecars, self.ordered_services))

    @property
    def want_xray(self) -> bool:
        return any([service.x_ray for service in self.services])

    def init_family(self) -> None:
        """
        Initializes the family after all services in the docker-compose definition have been assigned.

        The only containers that might then be added will be sidecars which won't influence
        launch type, capacity providers or anything else than the ECS Task Definition (CPU/RAM | ProxySettings)
        """
        self.set_services_to_services_dependencies()
        self.set_update_containers_priority()

        self.service_compute.set_update_launch_type()
        self.service_compute.set_update_capacity_providers()

        define_family_runtime_parameters(self)

        self.task_compute = TaskCompute(self)
        self.service_scaling = ServiceScaling(self)

    def init_task_definition(self):
        """
        Initialize the ECS TaskDefinition

        * Sets Compute settings
        * Sets the TaskDefinition using current services/ContainerDefinitions
        * Update the logging configuration for the containers.
        """
        self.task_compute.set_task_compute_parameter()
        self.set_task_definition()

    def set_task_definition(self):
        """
        Function to set or update the task definition

        :param self: the self of services
        """
        self.task_definition = TaskDefinition(
            TASK_T,
            template=self.template,
            Cpu=If(
                ecs_conditions.USE_FARGATE_CON_T,
                ecs_params.FARGATE_CPU,
                self.task_compute.cfn_family_cpu,
            ),
            Memory=If(
                ecs_conditions.USE_FARGATE_CON_T,
                ecs_params.FARGATE_RAM,
                self.task_compute.cfn_family_ram,
            ),
            NetworkMode=If(
                ecs_conditions.USE_WINDOWS_OS_T,
                NoValue,
                If(
                    ecs_conditions.USE_FARGATE_CON_T,
                    "awsvpc",
                    Ref(ecs_params.NETWORK_MODE),
                ),
            ),
            EphemeralStorage=If(
                ecs_conditions.USE_FARGATE_CON_T,
                EphemeralStorage(SizeInGiB=self.task_ephemeral_storage),
                NoValue,
            )
            if 0 < self.task_ephemeral_storage >= 21
            else NoValue,
            InferenceAccelerators=NoValue,
            IpcMode=If(
                ecs_conditions.USE_WINDOWS_OS_T,
                NoValue,
                If(
                    ecs_conditions.USE_EC2_OR_EXTERNAL_LT_CON_T,
                    Ref(ecs_params.IPC_MODE),
                    NoValue,
                ),
            ),
            Family=Ref(ecs_params.SERVICE_NAME),
            TaskRoleArn=self.iam_manager.task_role.arn,
            ExecutionRoleArn=self.iam_manager.exec_role.arn,
            ContainerDefinitions=[s.container_definition for s in self.services],
            RequiresCompatibilities=ecs_conditions.use_external_lt_con(
                ["EXTERNAL"],
                If(
                    ecs_conditions.USE_FARGATE_CON_T,
                    ["FARGATE"],
                    If(ecs_conditions.USE_EC2_CON_T, ["EC2"], ["EC2", "FARGATE"]),
                ),
            ),
            RuntimePlatform=If(
                ecs_conditions.USE_FARGATE_CON_T,
                RuntimePlatform(
                    CpuArchitecture=Ref(ecs_params.RUNTIME_CPU_ARCHITECTURE),
                    OperatingSystemFamily=Ref(ecs_params.RUNTIME_OS_FAMILY),
                ),
                NoValue,
            ),
            Tags=Tags(
                {
                    "Name": Ref(ecs_params.SERVICE_NAME),
                    "Environment": Ref(AWS_STACK_NAME),
                    "compose-x::family": self.name,
                    "compose-x::logical_name": self.logical_name,
                }
            ),
        )
        for service in self.services:
            service.container_definition.DockerLabels.update(
                {
                    "container_name": service.container_name,
                    "ecs_task_family": Ref(ecs_params.SERVICE_NAME),
                }
            )

    def import_all_sidecars(self) -> None:
        """
        Once all services have been added from the ComposeXSettings looping over services, we import all sidecars
        Should be invoked only once.
        """
        set_xray(self)
        set_prometheus(self)
        self.set_services_family_links()

    def set_services_family_links(self):
        for service in self.ordered_services:
            if service.links:
                for link in service.links:
                    for _svc in self.ordered_services:
                        if _svc == service:
                            continue
                        if _svc.name in link:
                            service.family_links.append(link)
            if self.xray_service and self.xray_service.name not in service.family_links:
                service.family_links.append(self.xray_service.name)
            if (
                self.cwagent_service
                and self.cwagent_service.name not in service.family_links
            ):
                service.family_links.append(f"{self.cwagent_service.name}:cwagent")
            if service.family_links:
                setattr(
                    service.container_definition,
                    "Links",
                    If(
                        ecs_conditions.USE_WINDOWS_OS_T,
                        NoValue,
                        If(
                            ecs_conditions.USE_BRIDGE_NETWORKING_MODE_CON_T,
                            service.family_links,
                            NoValue,
                        ),
                    ),
                )

    def generate_outputs(self):
        """
        Generates a list of CFN outputs for the ECS Service and Task Definition
        """
        if self.service_networking.security_group:
            self.outputs.append(
                CfnOutput(
                    f"{self.logical_name}GroupId",
                    Value=GetAtt(self.service_networking.security_group, "GroupId"),
                )
            )
            self.outputs.append(
                CfnOutput(
                    ecs_params.SERVICE_SUBNETS.title,
                    Value=Join(",", self.service_networking.subnets_output),
                )
            )

        self.outputs.append(
            CfnOutput(self.task_definition.title, Value=Ref(self.task_definition))
        )
        if (
            self.service_scaling
            and self.service_scaling.scalable_target
            and self.service_scaling.scalable_target.title in self.template.resources
        ):
            self.outputs.append(
                CfnOutput(
                    self.service_scaling.scalable_target.title,
                    Value=Ref(self.service_scaling.scalable_target),
                )
            )
        add_outputs(self.template, self.outputs)

    def state_facts(self):
        """
        Function to display facts about the family.
        Similar to __repr__ but for logging the properties of the ComposeFamily
        """
        LOG.info(f"{self.name} - Hostname set to {self.family_hostname}")
        LOG.info(f"{self.name} - Ephemeral storage: {self.task_ephemeral_storage}")
        LOG.info(f"{self.name} - LaunchType set to {self.service_compute.launch_type}")
        LOG.info(
            f"{self.name} - TaskDefinition containers: "
            f"{[svc.name for svc in self.services]}"
        )

    def add_service(self, service: ComposeService):
        """
        Function to add new services (defined in the compose files). Not to use for managed sidecars
        :param ComposeService service:
        """
        from ecs_composex.ecs.service_networking.helpers import set_family_hostname

        from .task_execute_command import set_enable_execute_command

        self._compose_services.append(service)

        self.set_update_containers_priority()
        self.iam_manager.init_update_policies()
        # self.handle_logging()

        self.service_compute.set_update_launch_type()
        self.service_compute.set_update_capacity_providers()

        if self.task_definition and service.container_definition:
            self.task_definition.ContainerDefinitions.append(
                service.container_definition
            )
            self.set_secrets_access()
        self.set_task_ephemeral_storage()
        set_enable_execute_command(self)
        set_family_hostname(self)

    def add_managed_sidecar(self, service: ComposeService):
        """
        Adds a new container/service to the Task Family and validates all settings that go along with the change.
        :param service:
        """

        if not isinstance(service, ComposeService) or not issubclass(
            type(service), ComposeService
        ):
            raise TypeError("service must be", ComposeService, "Got", type(service))
        if self.managed_sidecars and service.name in [
            svc.name for svc in self.managed_sidecars
        ]:
            LOG.debug(
                f"{self.name} - container service {service.name} is already set. Skipping"
            )
            return
        self.managed_sidecars.append(service)
        if self.task_definition and service.container_definition:
            self.task_definition.ContainerDefinitions.append(
                service.container_definition
            )
            self.set_secrets_access()
        self.iam_manager.init_update_policies()
        # self.handle_logging()

        self.service_compute.set_update_launch_type()
        self.service_compute.set_update_capacity_providers()
        self.task_compute.set_task_compute_parameter()

    def finalize_services_networking_settings(self, settings: ComposeXSettings) -> None:
        """
        Final pass on the service network settings
        """
        if settings.networks and self.service_networking.networks:
            update_family_subnets(self, settings)
        for service in chain(self.managed_sidecars, self.ordered_services):
            if service.ports or service.expose_ports:
                setattr(
                    service.container_definition,
                    "PortMappings",
                    service.define_port_mappings(),
                )

    def init_network_settings(
        self, settings: ComposeXSettings, vpc_stack: ComposeXStack
    ) -> None:
        """
        Once we have figured out the compute settings (EXTERNAL vs other)
        """
        from ecs_composex.ecs.service_networking.helpers import add_security_group

        self.service_networking = ServiceNetworking(self)
        self.finalize_services_networking_settings(settings)
        if self.service_compute.launch_type == "EXTERNAL":
            LOG.debug(f"{self.name} Ingress cannot be set (EXTERNAL mode). Skipping")
        else:
            if vpc_stack.vpc_resource.mappings:
                self.stack.set_vpc_params_from_vpc_lookup(vpc_stack, settings)
            else:
                self.stack.set_vpc_parameters_from_vpc_stack(vpc_stack, settings)
            add_security_group(self)
            self.service_networking.ingress.set_aws_sources_ingress(
                settings,
                self.logical_name,
                GetAtt(self.service_networking.security_group, "GroupId"),
            )
            self.service_networking.ingress.set_ext_sources_ingress(
                self.logical_name,
                GetAtt(self.service_networking.security_group, "GroupId"),
            )
            self.service_networking.ingress.associate_aws_ingress_rules(self.template)
            self.service_networking.ingress.associate_ext_ingress_rules(self.template)
            self.service_networking.add_self_ingress()

    def finalize_family_settings(self):
        """
        Once all services have been added, we add the sidecars and deal with appropriate permissions and settings
        Will add xray / prometheus sidecars
        """
        from .family_helpers import set_service_dependency_on_all_iam_policies

        self.add_containers_images_cfn_parameters()
        self.task_compute.set_task_compute_parameter()
        self.task_compute.unlock_compute_for_main_container()

        set_service_dependency_on_all_iam_policies(self)
        if self.service_compute.launch_type == "EXTERNAL":
            if hasattr(self.ecs_service.ecs_service, "LoadBalancers"):
                setattr(self.ecs_service.ecs_service, "LoadBalancers", NoValue)
            if hasattr(self.ecs_service.ecs_service, "ServiceRegistries"):
                setattr(self.ecs_service.ecs_service, "ServiceRegistries", NoValue)
            for container in self.task_definition.ContainerDefinitions:
                if hasattr(container, "LinuxParameters"):
                    parameters = getattr(container, "LinuxParameters")
                    setattr(parameters, "InitProcessEnabled", False)
        if (
            self.ecs_service.ecs_service
            and self.ecs_service.ecs_service.title in self.template.resources
        ) and (
            self.service_scaling
            and self.service_scaling.scalable_target
            and self.service_scaling.scalable_target.title
            not in self.template.resources
        ):
            self.template.add_resource(self.service_scaling.scalable_target)
        self.generate_outputs()
        service_configs = [
            [0, service]
            for service in chain(self.managed_sidecars, self.ordered_services)
        ]
        handle_same_task_services_dependencies(service_configs)
        self.set_add_region_when_external()

    def set_add_region_when_external(self):
        from troposphere.ecs import Environment

        env_var_to_add = Environment(Name="AWS_DEFAULT_REGION", Value=Region)
        region_conditional = If(
            ecs_conditions.USE_EXTERNAL_LT_T, env_var_to_add, NoValue
        )
        for service in self.services:
            environment = getattr(service.container_definition, "Environment")
            if (
                not environment
                or environment == NoValue
                or not isinstance(environment, list)
            ):
                environment = []
                setattr(service.container_definition, "Environment", environment)
            if "AWS_DEFAULT_REGION" not in [
                _env.Name for _env in environment if isinstance(_env, Environment)
            ]:
                environment.append(region_conditional)

    def set_services_to_services_dependencies(self):
        """
        Method to iterate over each depends_on service set in the family services and add them up

        :return:
        """
        for service in self.services:
            if service.depends_on:
                for service_depends_on in service.depends_on:
                    if service_depends_on not in self.services_depends_on:
                        self.services_depends_on.append(service_depends_on)

    def set_task_ephemeral_storage(self):
        """
        If any service ephemeral storage is defined above, sets the ephemeral storage to the maximum of them.
        """
        max_storage = max(service.ephemeral_storage for service in self.services)
        if max_storage >= 21:
            self.task_ephemeral_storage = max_storage

    def set_enable_execute_command(self) -> None:
        """
        Sets necessary settings to enable ECS Execute Command
        ECS Anywhere support since 2022-01-24
        """
        from .task_execute_command import set_enable_execute_command

        set_enable_execute_command(self)

    def apply_ecs_execute_command_permissions(self, settings: ComposeXSettings) -> None:
        """
        Method to set the IAM Policies in place to allow ECS Execute SSM and Logging

        :param settings:
        :return:
        """
        from .task_execute_command import apply_ecs_execute_command_permissions

        apply_ecs_execute_command_permissions(self, settings)

    def handle_alarms(self) -> None:
        from ecs_composex.ecs.service_alarms import handle_alarms

        handle_alarms(self)

    def handle_logging(self, settings: ComposeXSettings):
        """
        Method to go over each service logging configuration and accordingly define the IAM permissions needed for
        the exec/task role
        """
        self.logging = FamilyLogging(self)
        self.logging.init_family_services_log_configuration()
        wants_firelens = [
            service
            for service in self.ordered_services
            if service.logging.uses_firelens
        ]
        self.logging.handle_awslogs_logging(wants_firelens)
        if wants_firelens:
            self.logging.handle_firelens(settings)
        self.logging.update_cw_log_retention()

    def set_update_containers_priority(self) -> None:
        """
        Method to sort out the containers dependencies and create the containers definitions based on the configs.
        """
        service_configs = [
            [0, service]
            for service in list(chain(self._compose_services, self.managed_sidecars))
        ]
        handle_same_task_services_dependencies(service_configs)
        ordered_containers_config = sorted(service_configs, key=lambda i: i[0])
        self.ordered_services = [s[1] for s in ordered_containers_config]
        ensure_essential_containers(self)

    def set_secrets_access(self):
        """
        Method to handle secrets permissions access
        """
        if not self.iam_manager.exec_role or not self.iam_manager.task_role:
            return
        secrets = []
        for service in self.services:
            for secret in service.secrets:
                secrets.append(secret)
        if secrets:
            assign_secrets_to_roles(
                secrets,
                self.iam_manager.exec_role.cfn_resource,
                self.iam_manager.task_role.cfn_resource,
            )

    def add_containers_images_cfn_parameters(self):
        """
        Adds parameters to the stack and set values for each service/container in the family definition
        """
        if not self.template or not self.stack:
            return
        images_parameters = []
        for service in chain(self.managed_sidecars, self.ordered_services):
            if service.image.image_param.title not in self.stack.Parameters:
                if isinstance(service.image.image, str):
                    self.stack.Parameters.update(
                        {service.image.image_param.title: service.image.image}
                    )
                elif isinstance(service.image.image, Ref):
                    LOG.debug(f"{service.name} image is Parameter already.")
                images_parameters.append(service.image.image_param)
        add_parameters(self.template, images_parameters)

    def validate_compute_configuration_for_task(self, settings):
        from ecs_composex.ecs_cluster.ecs_family_helpers import (
            validate_compute_configuration_for_task,
        )

        validate_compute_configuration_for_task(self, settings)


class ServiceStack(ComposeXStack):
    """
    Class to identify specifically a service stack
    """
