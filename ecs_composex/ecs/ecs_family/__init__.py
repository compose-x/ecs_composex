#   -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Package to manage an ECS "Family" Task and Service definition
"""

import re

from troposphere import AWS_STACK_NAME, GetAtt, If, Join, NoValue
from troposphere import Output as CfnOutput
from troposphere import Ref, Tags
from troposphere.ecs import EphemeralStorage, RuntimePlatform, TaskDefinition

from ecs_composex.common import LOG, add_outputs, add_parameters
from ecs_composex.compose.compose_services import ComposeService
from ecs_composex.ecs import ecs_conditions, ecs_params
from ecs_composex.ecs.ecs_family.family_helpers import (
    handle_same_task_services_dependencies,
    set_ecs_cluster_logging_access,
)
from ecs_composex.ecs.ecs_params import AWS_XRAY_IMAGE, TASK_T
from ecs_composex.ecs.service_compute import ServiceCompute
from ecs_composex.ecs.service_networking import ServiceNetworking
from ecs_composex.ecs.service_scaling import ServiceScaling
from ecs_composex.ecs.task_iam import TaskIam
from ecs_composex.vpc.vpc_params import APP_SUBNETS

from .family_helpers import assign_secrets_to_roles, define_essential_containers
from .family_template import set_template
from .task_compute_helpers import set_task_compute_parameter
from .task_runtime import define_family_runtime_parameters


class ComposeFamily(object):
    """
    Class to group services logically to create the final ECS Task and Service definitions

    Processing order

    * Import all services
    * Define capacity providers
    * Define LaunchType

    :ivar list[ecs_composex.compose.compose_services.ComposeService] services: List of the Services part of the family
    :ivar ecs_composex.ecs.ecs_service.Service ecs_service: ECS Service settings
    :ivar ecs_composex.ecs.task_iam.TaskIam iam_manager:
    """

    default_launch_type = "EC2"
    xray_service_name = "xray-daemon"

    def __init__(self, services, family_name):
        self.services = services
        self.ordered_services = []
        self.ignored_services = []
        self.name = family_name
        self.logical_name = re.sub(r"[^a-zA-Z0-9]+", "", family_name)
        self.iam_manager = TaskIam(self)
        self.task_cpu = 0
        self.task_memory = 0
        self.family_hostname = self.name.replace("_", "-").lower()
        self.services_depends_on = []
        self.template = None
        set_template(self)
        self.stack = None
        self.stack_parameters = {}
        self.task_definition = None
        self.service_definition = None
        self.service_tags = None
        self.task_ephemeral_storage = 0
        self.family_network_mode = None
        self.enable_execute_command = False
        self.scalable_target = None
        self.ecs_service = None
        self.runtime_cpu_arch = None
        self.runtime_os_family = None
        self.launch_type = self.default_launch_type
        self.outputs = []
        self.task_logging_options = {}
        self.alarms = {}
        self.predefined_alarms = {}
        self.ecs_capacity_providers = []
        self.target_groups = []

        self.set_xray()
        self.set_prometheus()
        self.sort_container_configs()
        self.service_compute = ServiceCompute(self)

        define_family_runtime_parameters(self)

        self.set_initial_services_dependencies()
        self.iam_manager.init_update_policies()
        self.add_containers_images_cfn_parameters()

        self.service_scaling = ServiceScaling(self)
        self.service_networking = ServiceNetworking(self)

    def init_task_definition(self):
        """
        Initialize the ECS TaskDefinition

        * Sets Compute settings
        * Sets the TaskDefinition using current services/ContainerDefinitions
        * Update the logging configuration for the containers.
        """
        set_task_compute_parameter(self)
        self.set_task_definition()
        self.refresh_container_logging_definition()

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
                self.task_cpu if self.task_cpu else NoValue,
            ),
            Memory=If(
                ecs_conditions.USE_FARGATE_CON_T,
                ecs_params.FARGATE_RAM,
                self.task_memory if self.task_memory else NoValue,
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
                ecs_conditions.USE_WINDOWS_OR_FARGATE_T,
                NoValue,
                Ref(ecs_params.IPC_MODE),
            ),
            Family=Ref(ecs_params.SERVICE_NAME),
            TaskRoleArn=self.iam_manager.task_role.arn,
            ExecutionRoleArn=self.iam_manager.exec_role.arn,
            ContainerDefinitions=[s.container_definition for s in self.services],
            RequiresCompatibilities=ecs_conditions.use_external_lt_con(
                ["EXTERNAL"], ["EC2", "FARGATE"]
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
                    APP_SUBNETS.title,
                    Value=Join(",", Ref(APP_SUBNETS)),
                )
            )

        self.outputs.append(
            CfnOutput(self.task_definition.title, Value=Ref(self.task_definition))
        )
        if (
            self.scalable_target
            and self.scalable_target.title in self.template.resources
        ):
            self.outputs.append(
                CfnOutput(self.scalable_target.title, Value=Ref(self.scalable_target))
            )
        add_outputs(self.template, self.outputs)

    def state_facts(self):
        """
        Function to display facts about the family.
        Similar to __repr__ but for logging the properties of the ComposeFamily
        """
        LOG.info(f"{self.name} - Hostname set to {self.family_hostname}")
        LOG.info(f"{self.name} - Ephemeral storage: {self.task_ephemeral_storage}")
        LOG.info(f"{self.name} - LaunchType set to {self.launch_type}")
        LOG.info(
            f"{self.name} - TaskDefinition containers: {[svc.name for svc in self.services]}"
        )

    def add_security_group(self):
        """
        Creates a new EC2 SecurityGroup and assigns to ecs_service.network_settings
        Adds the security group to the family template resources.
        """
        from ecs_composex.ecs.service_networking.helpers import add_security_group

        add_security_group(family=self)

    def add_service_as_task_container(self, service):
        """
        Adds a new container/service to the Task Family and validates all settings that go along with the change.
        :param service:
        """
        from .task_execute_command import set_enable_execute_command

        if service.name in [svc.name for svc in self.services]:
            LOG.debug(
                f"{self.name} - container service {service.name} is already set. Skipping"
            )
            return
        self.services.append(service)
        if self.task_definition and service.container_definition:
            self.task_definition.ContainerDefinitions.append(
                service.container_definition
            )
            self.set_secrets_access()
        self.set_task_ephemeral_storage()
        set_enable_execute_command(self)
        self.refresh()

    def refresh(self):
        """
        Refresh the ComposeFamily settings as a result of a change
        """
        from ecs_composex.ecs.service_networking.helpers import set_family_hostname

        self.sort_container_configs()
        self.service_compute.set_update_launch_type()
        self.service_compute.set_update_capacity_providers()
        define_family_runtime_parameters(self)
        self.iam_manager.init_update_policies()
        self.handle_logging()
        self.add_containers_images_cfn_parameters()
        set_task_compute_parameter(self)
        set_family_hostname(self)

    def finalize_services_networking_settings(self):
        for service in self.services:
            if service.ports or service.expose_ports:
                setattr(
                    service.container_definition,
                    "PortMappings",
                    service.define_port_mappings(),
                )

    def finalize_family_settings(self):
        """
        Once all services have been added, we add the sidecars and deal with appropriate permissions and settings
        Will add xray / prometheus sidecars
        """
        from .family_helpers import set_service_dependency_on_all_iam_policies

        set_service_dependency_on_all_iam_policies(self)
        self.set_xray()
        self.set_prometheus()
        self.finalize_services_networking_settings()
        if self.launch_type == "EXTERNAL":
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
            self.scalable_target
            and self.scalable_target.title not in self.template.resources
        ):
            self.template.add_resource(self.scalable_target)
        self.generate_outputs()

    def set_initial_services_dependencies(self):
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
        max_storage = max([service.ephemeral_storage for service in self.services])
        if max_storage >= 21:
            self.task_ephemeral_storage = max_storage

    def set_enable_execute_command(self) -> None:
        """
        Sets necessary settings to enable ECS Execute Command
        ECS Anywhere support since 2022-01-24
        """
        from .task_execute_command import set_enable_execute_command

        set_enable_execute_command(self)

    def apply_ecs_execute_command_permissions(self, settings) -> None:
        """
        Method to set the IAM Policies in place to allow ECS Execute SSM and Logging

        :param settings:
        :return:
        """
        from .task_execute_command import apply_ecs_execute_command_permissions

        apply_ecs_execute_command_permissions(self, settings)

    def set_xray(self):
        """
        Automatically adds the xray-daemon sidecar to the task definition.

        Evaluates if any of the services x_ray is True to add.
        If any(True) then checks whether the xray-daemon container is already in the services.
        """
        if self.xray_service_name not in [
            service.name for service in self.services
        ] and any([service.x_ray for service in self.services]):
            xray_service = ComposeService(
                "xray-daemon",
                {
                    "image": AWS_XRAY_IMAGE,
                    "deploy": {
                        "resources": {"limits": {"cpus": 0.03125, "memory": "256M"}},
                    },
                    "x-iam": {
                        "ManagedPolicyArns": [
                            "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
                        ]
                    },
                },
            )
            xray_service.is_aws_sidecar = True
            self.add_service_as_task_container(xray_service)
            if xray_service.name not in self.ignored_services:
                self.ignored_services.append(xray_service)
            self.update_xray_service_dependencies(xray_service)
        else:
            self.update_xray_service_dependencies()

    def update_xray_service_dependencies(self, xray_service=None):
        if not xray_service:
            for service in self.services:
                if service.name == self.xray_service_name:
                    xray_service = service
                    break
            else:
                raise AttributeError(
                    "Failed to identify the already defined x-ray service",
                    [svc.name for svc in self.services],
                )

        for service in self.services:
            if service.is_aws_sidecar:
                continue
            if xray_service.name not in service.depends_on:
                service.depends_on.append(xray_service.name)
                LOG.info(
                    f"{self.name} - Adding xray-daemon as dependency to {service.name}"
                )

    def handle_alarms(self) -> None:
        from ecs_composex.ecs.service_alarms import handle_alarms

        handle_alarms(self)

    def handle_logging(self):
        """
        Method to go over each service logging configuration and accordingly define the IAM permissions needed for
        the exec role
        """
        from .task_logging import handle_logging

        handle_logging(self)

    def sort_container_configs(self):
        """
        Method to sort out the containers dependencies and create the containers definitions based on the configs.
        :return:
        """
        service_configs = [[0, service] for service in self.services]
        handle_same_task_services_dependencies(service_configs)
        ordered_containers_config = sorted(service_configs, key=lambda i: i[0])
        self.ordered_services = [s[1] for s in ordered_containers_config]
        define_essential_containers(self, ordered_containers_config)

        for service in self.services:
            self.stack_parameters.update(service.container_parameters)

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
        if not self.template:
            return
        images_parameters = []
        for service in self.services:
            self.stack_parameters.update({service.image_param.title: service.image})
            images_parameters.append(service.image_param)
        add_parameters(self.template, images_parameters)

    def refresh_container_logging_definition(self):
        for service in self.services:
            c_def = service.container_definition
            logging_def = c_def.LogConfiguration
            logging_def.Options.update(self.task_logging_options)

    def update_family_subnets(self, settings):
        """
        Method to update the stack parameters

        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        from ecs_composex.ecs.service_networking.helpers import update_family_subnets

        update_family_subnets(self, settings)

    def upload_services_env_files(self, settings):
        from ecs_composex.compose.compose_services.env_files_helpers import (
            upload_services_env_files,
        )

        upload_services_env_files(self, settings)

    def set_repository_credentials(self, settings):
        """
        Method to go over each service and identify which ones have credentials to pull the Docker image from a private
        repository

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        from ecs_composex.compose.compose_secrets.ecs_family_helpers import (
            set_repository_credentials,
        )

        set_repository_credentials(self, settings)

    def set_volumes(self) -> None:
        """
        Method to create the volumes definition to the Task Definition
        """
        from ecs_composex.compose.compose_volumes.ecs_family_helpers import set_volumes

        set_volumes(self)

    def validate_compute_configuration_for_task(self, settings):
        from ecs_composex.ecs.ecs_cluster.ecs_family_helpers import (
            validate_compute_configuration_for_task,
        )

        validate_compute_configuration_for_task(self, settings)

    def set_prometheus(self) -> None:
        from ecs_composex.ecs.ecs_prometheus import set_prometheus

        set_prometheus(self)
