# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Main module to generate a full stack with VPC, Cluster, Compute, Services and all X- AWS resources.
"""

import re
import warnings
from importlib import import_module

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_STACK_NAME, Ref

from ecs_composex.cloudmap.cloudmap_stack import x_cloud_lookup_and_new_vpc
from ecs_composex.common import LOG, NONALPHANUM, add_update_mapping, init_template
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import X_AWS_KEY, X_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import add_all_tags
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.compose.x_resources.services_resources import ServicesXResource
from ecs_composex.dashboards.dashboards_stack import XStack as DashboardsStack
from ecs_composex.ecs.ecs_cluster import add_ecs_cluster
from ecs_composex.ecs.ecs_cluster.helpers import set_ecs_cluster_identifier
from ecs_composex.ecs.ecs_stack import add_compose_families
from ecs_composex.ecs.helpers import (
    add_iam_dependency,
    handle_families_cross_dependencies,
    set_families_ecs_service,
    update_families_network_ingress,
    update_families_networking_settings,
)
from ecs_composex.iam.iam_stack import XStack as IamStack
from ecs_composex.vpc.helpers import (
    define_vpc_settings,
    update_network_resources_vpc_config,
)
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


def get_mod_class(module_name):
    """
    Function to get the XModule class for a specific ecs_composex module

    :param str module_name: Name of the x-module we are looking for.
    :return: the_class, maps to the main class for the given x-module
    """
    composex_module_name = f"ecs_composex.{module_name}.{module_name}_stack"
    LOG.debug(composex_module_name)
    the_class = None
    try:
        res_module = import_module(composex_module_name)
        LOG.debug(res_module)
        try:
            the_class = getattr(res_module, "XStack")
            return the_class
        except AttributeError:
            LOG.info(f"No XStack class for {module_name} found - skipping")
            return None
    except ImportError as error:
        LOG.error(f"Failure to process the module {composex_module_name}")
        LOG.error(error)
    return the_class


def invoke_x_to_ecs(module_name, services_stack, resource, settings) -> None:
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
            settings.compose_content[composex_key],
            services_stack,
            resource,
            settings,
        )


def apply_x_configs_to_ecs(settings, root_stack) -> None:
    """
    Function that evaluates only the x- resources of the root template and iterates over the resources.
    If there is an implemented module in ECS ComposeX for that resource_stack to map to the ECS Services, it will
    execute the function available in the module to apply defined settings to the services stack.

    The root_stack is used as the parent stack to the services.

    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param ecs_composex.ecs.ServicesStack root_stack: root stack for services.
    """
    for resource in settings.x_resources:
        if (
            isinstance(resource, ServicesXResource)
            or issubclass(type(resource), ServicesXResource)
        ) and hasattr(resource, "to_ecs"):
            resource.to_ecs(settings, root_stack)

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
    settings, root_stack, vpc_stack, env_resources_only: bool = False
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


def process_x_class(root_stack, settings, key):
    """
    Process the resource class module for its respective Compose stack
    """
    res_type = RES_REGX.sub("", key)
    xclass = get_mod_class(res_type)
    parameters = {ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME)}
    LOG.debug(xclass)
    if not xclass:
        LOG.info(f"Class for {res_type} not found")
        xstack = None
    else:
        xstack = xclass(
            res_type.strip(),
            settings=settings,
            Parameters=parameters,
        )
    if xstack and xstack.is_void:
        settings.x_resources_void.append({res_type: xstack})
    elif (
        xstack
        and hasattr(xstack, "title")
        and hasattr(xstack, "stack_template")
        and not xstack.is_void
    ):
        root_stack.stack_template.add_resource(xstack)


def add_x_env_resources(root_stack, settings) -> None:
    """
    Processes the modules / resources that are defining the environment settings
    """
    for key in settings.compose_content:
        if (
            key.startswith(X_KEY)
            and key in ENV_RESOURCES
            and not re.match(X_AWS_KEY, key)
        ):
            LOG.info(f"{settings.name} - Processing {key}")
            process_x_class(root_stack, settings, key)


def add_x_resources(root_stack, settings) -> None:
    """
    Function to add each X resource from the compose file
    For each resource type, will create a ComposeXStack and add the resources to it.
    """
    for key in settings.compose_content:
        if (
            key.startswith(X_KEY)
            and key not in IGNORED_X_KEYS
            and key not in ENV_RESOURCES
            and not re.match(X_AWS_KEY, key)
        ):
            process_x_class(root_stack, settings, key)


def create_root_stack(settings) -> ComposeXStack:
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


def set_all_mappings_to_root_stack(root_stack, settings):
    """
    Adds all of the mappings to the root stack

    :param ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    """
    for mapping_key, mapping in settings.mappings.items():
        add_update_mapping(root_stack.stack_template, mapping_key, mapping)


def generate_full_template(settings):
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
    root_stack = create_root_stack(settings)
    add_ecs_cluster(root_stack, settings)
    iam_stack = root_stack.stack_template.add_resource(IamStack("iam", settings))
    add_x_env_resources(root_stack, settings)
    add_x_resources(root_stack, settings)
    add_compose_families(root_stack, settings)
    vpc_stack = VpcStack("vpc", settings)
    define_vpc_settings(settings, vpc_stack, root_stack)

    if vpc_stack.vpc_resource and (
        vpc_stack.vpc_resource.cfn_resource or vpc_stack.vpc_resource.mappings
    ):
        settings.set_networks(vpc_stack)
    # if settings.use_appmesh:
    #     from ecs_composex.appmesh.appmesh_mesh import Mesh
    #
    #     mesh = Mesh(
    #         settings.compose_content["x-appmesh"],
    #         root_stack,
    #         settings,
    #     )
    #     mesh.render_mesh_template(root_stack, settings)

    x_cloud_lookup_and_new_vpc(settings, vpc_stack)

    for family in settings.families.values():
        family.init_network_settings(settings, vpc_stack)

    handle_families_cross_dependencies(settings, root_stack)
    update_network_resources_vpc_config(settings, vpc_stack)
    set_families_ecs_service(settings)

    apply_x_resource_to_x(settings, root_stack, vpc_stack, env_resources_only=True)
    apply_x_configs_to_ecs(
        settings,
        root_stack,
    )
    apply_x_resource_to_x(settings, root_stack, vpc_stack)

    if keyisset("x-dashboards", settings.compose_content):
        root_stack.stack_template.add_resource(DashboardsStack("dashboards", settings))
    for family in settings.families.values():
        add_iam_dependency(iam_stack, family)
        family.set_enable_execute_command()
        if family.enable_execute_command:
            family.apply_ecs_execute_command_permissions(settings)
        family.finalize_family_settings()
        family.state_facts()
    set_ecs_cluster_identifier(root_stack, settings)
    add_all_tags(root_stack.stack_template, settings)
    set_all_mappings_to_root_stack(root_stack, settings)
    return root_stack
