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
Main module to generate a full stack with VPC, Cluster, Compute, Services and all X- AWS resources.
"""

import re
from importlib import import_module

from troposphere import Ref, If, AWS_STACK_NAME
from troposphere.ecs import Cluster

from ecs_composex.appmesh import Mesh
from ecs_composex.common import (
    LOG,
    add_parameters,
    build_parameters_file,
)
from ecs_composex.common import (
    build_template,
    keyisset,
    validate_resource_title,
)
from ecs_composex.common import cfn_conditions
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T,
    USE_FLEET,
    USE_FLEET_T,
    USE_ONDEMAND,
    USE_ONDEMAND_T,
    USE_CLOUDMAP_T,
    USE_CLOUDMAP,
)
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import generate_tags_parameters, add_all_tags
from ecs_composex.compute.compute_params import (
    TARGET_CAPACITY_T,
    TARGET_CAPACITY,
    MIN_CAPACITY_T,
)
from ecs_composex.compute.compute_stack import ComputeStack
from ecs_composex.ecs import ServicesStack
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_conditions import (
    GENERATED_CLUSTER_NAME_CON_T,
    GENERATED_CLUSTER_NAME_CON,
    CLUSTER_NAME_CON_T,
    CLUSTER_NAME_CON,
)
from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME_T,
    CLUSTER_NAME,
    RES_KEY as SERVICES_KEY,
)
from ecs_composex.ecs.ecs_template import define_services_families
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_stack import VpcStack

RES_REGX = re.compile(r"(^([x-]+))")
ROOT_CLUSTER_NAME = "EcsCluster"
COMPUTE_STACK_NAME = "Ec2Compute"
VPC_STACK_NAME = "vpc"
MESH_TITLE = "RootMesh"

VPC_ARGS = [
    vpc_params.PUBLIC_SUBNETS_T,
    vpc_params.APP_SUBNETS_T,
    vpc_params.STORAGE_SUBNETS_T,
    vpc_params.VPC_ID_T,
    vpc_params.VPC_MAP_ID_T,
]

SUPPORTED_X_MODULES = [
    f"{X_KEY}rds",
    "rds",
    f"{X_KEY}sqs",
    "sqs",
    f"{X_KEY}sns",
    "sns",
    f"{X_KEY}acm",
    "acm",
]
EXCLUDED_X_KEYS = [f"{X_KEY}configs", f"{X_KEY}tags", f"{X_KEY}appmesh", f"{X_KEY}vpc"]


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
        LOG.error(f"Failure to process the module {composex_module_name}")
        LOG.error(error)
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
            the_class = getattr(res_module, "XResource")
            return the_class
        except AttributeError:
            LOG.info(f"No XResource class for {module_name} found - skipping")
            return None
    except ImportError as error:
        LOG.error(f"Failure to process the module {composex_module_name}")
        LOG.error(error)
    return the_class


def generate_x_resources_policies(resources, resource_type, function, **kwargs):
    """
    Function to create the policies for the resources of a given type

    :param resources: resources to go over from docker ComposeX file
    :type resources: dict
    :param resource_type: resource type, ie. sqs
    :type resource_type: str
    :param function: the function to call to get IAM policies to add to ecs_service role
    :type function: function pointer
    :param kwargs: optional arguments
    :type kwargs: dict

    :return: policies for each resource of given resource type to use for roles
    :rtype: dict
    """
    mod_policies = {}
    for resource_name in resources:
        assert validate_resource_title(resource_name, resource_type)
        resource = resources[resource_name]

        if keyisset("Services", resource):
            mod_policies[resource_name] = function(resource_name, resource, **kwargs)
    return mod_policies


def apply_x_configs_to_ecs(
    settings, root_template, services_stack, services_families, **kwargs
):
    """
    Function that evaluates only the x- resources of the root template and iterates over the resources.
    If there is an implemented module in ECS ComposeX for that resource to map to the ECS Services, it will
    execute the function available in the module to apply defined settings to the services stack.

    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param troposphere.Template root_template: The root template for ECS ComposeX
    :param ecs_composex.ecs.ServicesStack services_stack: root stack for services.
    :param dict kwargs: settings for building X related resources
    :param dict services_families: Families and services mappings
    """
    for resource_name in root_template.resources:
        resource = root_template.resources[resource_name]
        if (
            issubclass(type(resource), ComposeXStack)
            and resource_name in SUPPORTED_X_MODULES
        ):
            module = getattr(resource, "title")
            composex_key = f"x-{module}"
            ecs_function = get_mod_function(
                f"{module}.{module}_ecs", f"{module}_to_ecs"
            )
            if ecs_function:
                LOG.debug(ecs_function)
                ecs_function(
                    settings.compose_content[composex_key],
                    services_stack,
                    services_families,
                    resource,
                )


def apply_x_to_x_configs(root_template, settings):
    """
    Function to iterate over each XResource and trigger cross-x resources configurations functions

    :param troposphere.Template root_template: the ECS ComposeX root template
    :param ComposeXSettings settings: The execution settings
    :return:
    """
    for resource_name in root_template.resources:
        resource = root_template.resources[resource_name]
        if (
            issubclass(type(resource), ComposeXStack)
            and resource_name in SUPPORTED_X_MODULES
            and hasattr(resource, "add_xdependencies")
        ):
            resource.add_xdependencies(root_template, settings.compose_content)


def add_compute(root_template, settings, vpc_stack):
    """
    Function to add Cluster stack to root one. If any of the options related to compute resources are set in the CLI
    then this function will generate and add the compute template to the root stack template

    :param root_template: the root template
    :type root_template: troposphere.Template
    :param vpc_stack: the VPC stack if any to pull the attributes from
    :param ComposeXSettings settings: The settings for execution
    :return: compute_stack, the Compute stack
    :rtype: ComposeXStack
    """
    if not settings.create_compute:
        return None
    root_template.add_parameter(TARGET_CAPACITY)
    parameters = {
        ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME),
        TARGET_CAPACITY_T: Ref(TARGET_CAPACITY),
        MIN_CAPACITY_T: Ref(TARGET_CAPACITY),
        USE_FLEET_T: Ref(USE_FLEET),
        USE_ONDEMAND_T: Ref(USE_ONDEMAND),
    }
    compute_stack = ComputeStack(
        COMPUTE_STACK_NAME, settings=settings, parameters=parameters
    )
    if vpc_stack is not None:
        compute_stack.get_from_vpc_stack(vpc_stack)
    else:
        compute_stack.no_vpc_parameters()
    return root_template.add_resource(compute_stack)


def add_x_resources(root_template, settings, vpc_stack=None):
    """
    Function to add each X resource from the compose file
    """
    tcp_services = ["x-rds", "x-appmesh"]
    for key in settings.compose_content:
        if key.startswith(X_KEY) and key not in EXCLUDED_X_KEYS:
            res_type = RES_REGX.sub("", key)
            xclass = get_mod_class(res_type)
            parameters = {ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME)}
            LOG.debug(xclass)
            if not xclass:
                LOG.info(f"Class for {res_type} not found")
            else:
                xstack = xclass(
                    res_type.strip(), settings=settings, Parameters=parameters,
                )
                if vpc_stack and key in tcp_services:
                    xstack.get_from_vpc_stack(vpc_stack)
                root_template.add_resource(xstack)


def create_services(root_stack, settings):
    """
    Function to add the microservices root stack

    :param ComposeXSettings settings: The settings for execution
    """
    stack = ServicesStack("services", settings)
    if settings.create_cluster:
        stack.Parameters.update({ecs_params.CLUSTER_NAME_T: Ref(ROOT_CLUSTER_NAME)})
    else:
        stack.Parameters.update({ecs_params.CLUSTER_NAME_T: Ref(CLUSTER_NAME)})
    return root_stack.stack_template.add_resource(stack)


def add_ecs_cluster(template, depends_on=None):
    """
    Function to add the cluster to the root template.

    :param depends_on: list of dependencies for the object
    :type depends_on: list
    :param template: the root stack template
    :type template: troposphere.Template
    """
    template.add_condition(GENERATED_CLUSTER_NAME_CON_T, GENERATED_CLUSTER_NAME_CON)
    template.add_condition(CLUSTER_NAME_CON_T, CLUSTER_NAME_CON)
    if depends_on is None:
        depends_on = []
    try:
        from troposphere.ecs import CapacityProviderStrategyItem

        Cluster(
            ROOT_CLUSTER_NAME,
            template=template,
            ClusterName=If(
                CLUSTER_NAME_CON_T, Ref(AWS_STACK_NAME), Ref(CLUSTER_NAME_T)
            ),
            DependsOn=depends_on,
            CapacityProviders=["FARGATE", "FARGATE_SPOT"],
            DefaultCapacityProviderStrategy=[
                CapacityProviderStrategyItem(Weight=2, CapacityProvider="FARGATE_SPOT"),
                CapacityProviderStrategyItem(Weight=1, CapacityProvider="FARGATE"),
            ],
        )
    except ImportError as error:
        LOG.info("Capacity providers not yet available in troposphere")
        LOG.warning(error)
        Cluster(
            ROOT_CLUSTER_NAME,
            template=template,
            ClusterName=If(
                CLUSTER_NAME_CON_T, Ref(AWS_STACK_NAME), Ref(CLUSTER_NAME_T)
            ),
            DependsOn=depends_on,
        )


def init_root_template(stack_params, tags=None):
    """
    Function to initialize the root template

    :param stack_params: stack parameters
    :type stack_params: list
    :param tags: tags and parameters to add to the template
    :type tags: tuple

    :return: template
    :rtype: troposphere.Template
    """

    template = build_template(
        "Root template generated via ECS ComposeX",
        [USE_FLEET, USE_ONDEMAND, CLUSTER_NAME, USE_CLOUDMAP],
    )
    template.add_condition(
        cfn_conditions.USE_CLOUDMAP_CON_T, cfn_conditions.USE_CLOUDMAP_CON
    )
    template.add_condition(
        cfn_conditions.NOT_USE_CLOUDMAP_CON_T, cfn_conditions.NOT_USE_CLOUDMAP_CON
    )
    if tags and tags[0] and isinstance(tags[0], list):
        add_parameters(template, tags[0])
        for param in tags[0]:
            build_parameters_file(stack_params, param.title, param.Default)
    return template


def create_vpc_root(root_stack, settings):
    """
    Function to figure whether to create the VPC Stack and if not, set the parameters.

    :param root_stack:
    :param settings:
    :return:
    """
    if settings.create_vpc:
        vpc_stack = VpcStack(
            VPC_STACK_NAME,
            settings,
            **{
                "Parameters": {
                    ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME),
                    USE_CLOUDMAP_T: Ref(USE_CLOUDMAP),
                }
            },
        )
        return root_stack.stack_template.add_resource(vpc_stack)
    else:
        add_parameters(
            root_stack.stack_template,
            [
                vpc_params.VPC_ID,
                vpc_params.APP_SUBNETS,
                vpc_params.STORAGE_SUBNETS,
                vpc_params.PUBLIC_SUBNETS,
                vpc_params.VPC_MAP_ID,
                vpc_params.VPC_MAP_DNS_ZONE,
            ],
        )
        settings_params = {
            vpc_params.VPC_ID.title: getattr(settings, vpc_params.VPC_ID_T),
            vpc_params.APP_SUBNETS.title: getattr(settings, vpc_params.APP_SUBNETS_T),
            vpc_params.STORAGE_SUBNETS.title: getattr(
                settings, vpc_params.STORAGE_SUBNETS_T
            ),
            vpc_params.PUBLIC_SUBNETS.title: getattr(
                settings, vpc_params.PUBLIC_SUBNETS_T
            ),
            vpc_params.VPC_MAP_ID.title: settings.vpc_private_namespace_id,
            vpc_params.VPC_MAP_DNS_ZONE.title: "cluster.local",
        }
        root_stack.Parameters.update(settings_params)
    return None


def generate_full_template(settings):
    """
    Function to generate the root root_template

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return root_template: Template, params
    :rtype: root_template, list
    """
    stack_params = []
    tags_params = generate_tags_parameters(settings.compose_content)
    LOG.debug(settings)
    root_template = init_root_template(stack_params, tags_params)
    root_stack = ComposeXStack(settings.name, stack_template=root_template)
    root_stack.Parameters.update(settings.create_root_stack_parameters_from_input())
    depends_on = []
    vpc_stack = create_vpc_root(root_stack, settings)
    compute_stack = add_compute(root_stack.stack_template, settings, vpc_stack)
    services_families = define_services_families(settings.compose_content[SERVICES_KEY])
    services_stack = create_services(root_stack, settings)
    if vpc_stack:
        services_stack.get_from_vpc_stack(vpc_stack)

    if settings.cluster_name != CLUSTER_NAME.Default:
        root_stack.stack_parameters.update({CLUSTER_NAME_T: settings.cluster_name})

    if settings.create_cluster:
        add_ecs_cluster(root_template)
        depends_on.append(ROOT_CLUSTER_NAME)
        if settings.create_compute and compute_stack:
            compute_stack.DependsOn.append(ROOT_CLUSTER_NAME)

    add_x_resources(root_template, settings, vpc_stack=vpc_stack)
    apply_x_configs_to_ecs(settings, root_template, services_stack, services_families)
    apply_x_to_x_configs(root_template, settings)

    if keyisset("x-appmesh", settings.compose_content) and settings.create_vpc:
        mesh = Mesh(settings.compose_content["x-appmesh"], services_stack)
        mesh.render_mesh_template(services_stack)
    elif keyisset("x-appmesh", settings.compose_content) and not settings.create_vpc:
        LOG.warning(
            "ComposeX only supports appmesh if you create the VPC at the same time"
        )
    add_all_tags(root_template, tags_params)
    LOG.debug(stack_params)
    return root_stack
