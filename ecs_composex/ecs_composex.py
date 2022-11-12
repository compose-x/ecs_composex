# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module to generate a full stack with VPC, Cluster, Compute, Services and all X- AWS resources.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.compose.x_resources import XResource

import re
import warnings
from importlib import import_module

from troposphere import AWS_STACK_NAME, Ref

from ecs_composex.cloudmap.cloudmap_helpers import x_cloud_lookup_and_new_vpc
from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import add_all_tags
from ecs_composex.common.troposphere_tools import (
    add_resource,
    add_update_mapping,
    init_template,
)
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.compose.x_resources.services_resources import ServicesXResource
from ecs_composex.ecs.ecs_stack import add_compose_families
from ecs_composex.ecs.helpers import (
    add_iam_dependency,
    handle_families_cross_dependencies,
    set_families_ecs_service,
)
from ecs_composex.ecs_cluster import add_ecs_cluster
from ecs_composex.ecs_cluster.helpers import set_ecs_cluster_identifier
from ecs_composex.iam.iam_stack import XStack as IamStack
from ecs_composex.mods_manager import ModManager
from ecs_composex.resource_settings import map_resource_return_value_to_services_command
from ecs_composex.vpc.helpers import (
    define_vpc_settings,
    update_network_resources_vpc_config,
)
from ecs_composex.vpc.vpc_stack import Vpc
from ecs_composex.vpc.vpc_stack import XStack as VpcStack

RES_REGX = re.compile(r"(^([x-]+))")
COMPUTE_STACK_NAME = "Ec2Compute"
VPC_STACK_NAME = "vpc"
MESH_TITLE = "RootMesh"

IGNORED_X_KEYS = [
    f"{X_KEY}tags",
    f"{X_KEY}appmesh",
    f"{X_KEY}vpc",
    f"{X_KEY}cluster",
    f"{X_KEY}dashboards",
]

ENV_RESOURCE_MODULES = ["acm", "route53", "cloudmap"]
ENV_RESOURCES = [f"{X_KEY}{mode}" for mode in ENV_RESOURCE_MODULES]
DEPRECATED_RESOURCES = [(f"{X_KEY}dns", "0.17", ["x-route53", "x-cloudmap"])]


def get_mod_function(module_name, function_name):
    """
    Function to get function in a given module name from function_name

    :param module_name: the name of the module in ecs_composex to find and try to import
    :type module_name: str
    :param function_name: name of the function to try to get
    :type function_name: str

    :return: function, if found, from the module
    :rtype: function
    """
    composex_module_name = f"ecs_composex.{module_name}"
    LOG.debug(composex_module_name)
    function = None
    try:
        res_module = import_module(composex_module_name)
        LOG.debug(res_module)
        try:
            function = getattr(res_module, function_name)
            return function
        except AttributeError:
            LOG.info(f"No {function_name} function found - skipping")
    except ImportError as error:
        LOG.debug(f"Failure to process the module {composex_module_name}")
        LOG.debug(error)
    return function


def invoke_x_to_ecs(
    module_name: str,
    services_stack: ComposeXStack,
    resource: XResource,
    settings: ComposeXSettings,
) -> None:
    """
    Function to associate X resources to Services

    :param None,str module_name: The name of the module managing the resource type
    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param ecs_composex.ecs.ServicesStack services_stack: root stack for services.
    :param ecs_composex.common.stacks.ComposeXStack resource: The XStack resource of the module
    :return:
    """
    if module_name is None:
        module_name = resource.name
    composex_key = f"{X_KEY}{module_name}"
    ecs_function = get_mod_function(
        f"{module_name}.{module_name}_ecs", f"{module_name}_to_ecs"
    )
    if ecs_function:
        LOG.debug(ecs_function)
        ecs_function(
            settings.mod_manager.modules[composex_key].resources,
            services_stack,
            resource,
            settings,
        )


def apply_x_configs_to_ecs(
    settings: ComposeXSettings, root_stack: ComposeXStack, modules: ModManager
) -> None:
    """
    Function that evaluates only the x- resources of the root template and iterates over the resources.
    If there is an implemented module in ECS ComposeX for that resource_stack to map to the ECS Services, it will
    execute the function available in the module to apply defined settings to the services stack.

    The root_stack is used as the parent stack to the services.

    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param ecs_composex.ecs.ServicesStack root_stack: root stack for services.
    :param ecs_composex.mod_manager.ModManager modules:
    """
    for resource in settings.x_resources:
        if (
            isinstance(resource, (ServicesXResource, AwsEnvironmentResource))
            or issubclass(type(resource), (ServicesXResource, AwsEnvironmentResource))
        ) and hasattr(resource, "to_ecs"):
            resource.to_ecs(settings, modules, root_stack)
    for resource_stack in root_stack.stack_template.resources.values():
        if (
            issubclass(type(resource_stack), ComposeXStack)
            and not resource_stack.is_void
        ):
            invoke_x_to_ecs(None, root_stack, resource_stack, settings)

    for resource_stack in settings.x_resources_void:
        res_type = list(resource_stack.keys())[-1]
        invoke_x_to_ecs(res_type, root_stack, resource_stack[res_type], settings)


def apply_x_resource_to_x(
    settings: ComposeXSettings,
    root_stack: ComposeXStack,
    vpc_stack: ComposeXStack,
    env_resources_only: bool = False,
) -> None:
    """
    Goes over each x resource in the execution and execute logical association between the resources.
    If env_resources_only is true, only invokes handle_x_dependencies only for the AwsEnvironmentResource resources
    defined.

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :param ComposeXStack root_stack:
    :param ComposeXStack vpc_stack:
    :param bool env_resources_only: Whether to process the AwsEnvironmentResource first and link to other services.
    """
    for resource in settings.x_resources:
        if env_resources_only and not (
            issubclass(type(resource), AwsEnvironmentResource)
            or isinstance(resource, AwsEnvironmentResource)
        ):
            continue
        if hasattr(resource, "handle_x_dependencies"):
            resource.handle_x_dependencies(settings, root_stack)
    if vpc_stack and vpc_stack.vpc_resource:
        vpc_stack.vpc_resource.handle_x_dependencies(settings, root_stack)


def add_x_resources(settings: ComposeXSettings) -> None:
    """
    Processes the modules / resources that are defining the environment settings
    """
    for name, module in settings.mod_manager.modules.items():
        LOG.info(f"Processing {name}")
        x_stack = module.stack_class(
            module.mapping_key,
            settings=settings,
            module=module,
            Parameters={ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME)},
        )
        if x_stack and x_stack.is_void:
            settings.x_resources_void.append({module.res_key: x_stack})
        elif (
            x_stack
            and hasattr(x_stack, "title")
            and hasattr(x_stack, "stack_template")
            and not x_stack.is_void
        ):
            add_resource(settings.root_stack.stack_template, x_stack)


def create_root_stack(settings: ComposeXSettings) -> ComposeXStack:
    """
    Initializes the root stack template and ComposeXStack

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    """
    template = init_template("Root template generated via ECS ComposeX")
    template.add_mapping("ComposeXDefaults", {"ECS": {"PlatformVersion": "1.4.0"}})
    root_stack_title = NONALPHANUM.sub("", settings.name.title())
    root_stack = ComposeXStack(
        root_stack_title,
        stack_template=template,
        file_name=settings.name,
    )
    return root_stack


def deprecation_warning(settings):
    """
    Simple function to warn about deprecation of compose-x modules / x-resources
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    """
    for mod in DEPRECATED_RESOURCES:
        if mod[0] in settings.compose_content.keys():
            warnings.warn(
                f"{mod[0]} is deprecated since {mod[1]}. See {mod[2]} as alternatives",
                DeprecationWarning,
            )


def set_all_mappings_to_root_stack(
    root_stack: ComposeXStack, settings: ComposeXSettings
):
    """
    Adds all the mappings to the root stack

    :param ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    """
    for mapping_key, mapping in settings.mappings.items():
        add_update_mapping(root_stack.stack_template, mapping_key, mapping)


def generate_full_template(settings: ComposeXSettings):
    """
    Function to generate the root template and associate services, x-resources to each other.

    * Checks that the docker images and settings are correct before proceeding further
    * Create the root template / stack
    * Create/Find ECS Cluster
    * Create IAM Stack (services Roles and some policies)
    * Create/Find x-resources
    * Link services and x-resources
    * Associates services/family to root stack

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return root_template: Template, params
    :rtype: root_template, list
    """
    deprecation_warning(settings)
    LOG.info(
        f"Service families to process {[family.name for family in settings.families.values()]}"
    )
    settings.root_stack = create_root_stack(settings)
    for family in settings.families.values():
        family.stack.parent_stack = settings.root_stack
    add_ecs_cluster(settings)
    settings.mod_manager = ModManager(settings)
    settings.mod_manager.modules_repr()
    settings.mod_manager.init_mods_resources(settings)
    iam_stack = add_resource(
        settings.root_stack.stack_template, IamStack("iam", settings)
    )
    add_x_resources(settings)
    add_compose_families(settings)
    if "x-vpc" not in settings.mod_manager.modules:
        vpc_module = settings.mod_manager.load_module("x-vpc", {})
    else:
        vpc_module = settings.mod_manager.modules["x-vpc"]
    vpc_stack = VpcStack("vpc", settings, vpc_module)
    define_vpc_settings(settings, vpc_module, vpc_stack)
    if vpc_stack.vpc_resource and (
        vpc_stack.vpc_resource.cfn_resource or vpc_stack.vpc_resource.mappings
    ):
        settings.set_networks(vpc_stack)
    vpc_module.resources.update({"x-vpc": vpc_stack.vpc_resource})
    x_cloud_lookup_and_new_vpc(settings, vpc_stack)

    for family in settings.families.values():
        family.init_network_settings(settings, vpc_stack)

    handle_families_cross_dependencies(settings, settings.root_stack)
    update_network_resources_vpc_config(settings, vpc_stack)
    set_families_ecs_service(settings)

    apply_x_resource_to_x(
        settings, settings.root_stack, vpc_stack, env_resources_only=True
    )
    for family in settings.families.values():
        add_iam_dependency(iam_stack, family)
        family.set_enable_execute_command()
        if family.enable_execute_command:
            family.apply_ecs_execute_command_permissions(settings)
        family.import_all_sidecars()
        family.handle_logging(settings)

    apply_x_configs_to_ecs(settings, settings.root_stack, modules=settings.mod_manager)
    apply_x_resource_to_x(settings, settings.root_stack, vpc_stack)

    if settings.use_appmesh:
        from ecs_composex.appmesh.appmesh_mesh import Mesh

        mesh = Mesh(
            settings.compose_content["x-appmesh"],
            settings.root_stack,
            settings,
        )
        mesh.render_mesh_template(mesh.stack, settings)

    for family in settings.families.values():
        family.finalize_family_settings()
        map_resource_return_value_to_services_command(family, settings)
        family.state_facts()

    set_ecs_cluster_identifier(settings.root_stack, settings)
    add_all_tags(settings.root_stack.stack_template, settings)
    set_all_mappings_to_root_stack(settings.root_stack, settings)

    for resource in settings.x_resources:
        if hasattr(resource, "post_processing"):
            resource.post_processing(settings)

    settings.mod_manager.modules.clear()
    return settings.root_stack
