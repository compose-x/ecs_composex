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

from troposphere import Ref, AWS_STACK_NAME, GetAtt

from ecs_composex.acm.acm_params import RES_KEY as ACM_KEY
from ecs_composex.acm.acm_stack import init_acm_certs
from ecs_composex.appmesh.appmesh_mesh import Mesh
from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common import (
    build_template,
    keyisset,
)
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T,
    USE_FLEET,
    USE_FLEET_T,
    USE_ONDEMAND,
    USE_ONDEMAND_T,
)
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import add_all_tags
from ecs_composex.compute.compute_params import (
    TARGET_CAPACITY_T,
    TARGET_CAPACITY,
    MIN_CAPACITY_T,
)
from ecs_composex.compute.compute_stack import ComputeStack
from ecs_composex.dns import add_parameters_and_conditions as dns_inputs, DnsSettings
from ecs_composex.ecs import associate_services_to_root_stack
from ecs_composex.ecs.ecs_cluster import add_ecs_cluster
from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME,
    CLUSTER_T as ROOT_CLUSTER_NAME,
    CREATE_CLUSTER,
)
from ecs_composex.ecs.ecs_conditions import CREATE_CLUSTER_CON_T, CREATE_CLUSTER_CON
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_stack import add_vpc_to_root

RES_REGX = re.compile(r"(^([x-]+))")
COMPUTE_STACK_NAME = "Ec2Compute"
VPC_STACK_NAME = "vpc"
MESH_TITLE = "RootMesh"

SUPPORTED_X_MODULE_NAMES = [
    "rds",
    "sqs",
    "sns",
    "acm",
    "dynamodb",
    "kms",
    "s3",
    "elbv2",
    "docdb",
]

SUPPORTED_X_MODULES = [f"{X_KEY}{mod_name}" for mod_name in SUPPORTED_X_MODULE_NAMES]
EXCLUDED_X_KEYS = [
    f"{X_KEY}configs",
    f"{X_KEY}tags",
    f"{X_KEY}appmesh",
    f"{X_KEY}acm",
    f"{X_KEY}vpc",
    f"{X_KEY}dns",
    f"{X_KEY}cluster",
    f"{X_KEY}efs",
]
TCP_SERVICES = [f"{X_KEY}rds", f"{X_KEY}appmesh", f"{X_KEY}elbv2"]


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
            the_class = getattr(res_module, "XStack")
            return the_class
        except AttributeError:
            LOG.info(f"No XStack class for {module_name} found - skipping")
            return None
    except ImportError as error:
        LOG.error(f"Failure to process the module {composex_module_name}")
        LOG.error(error)
    return the_class


def invoke_x_to_ecs(module, settings, services_stack, resource):
    """
    Function to associate X resources to Services

    :param str module:
    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param ecs_composex.ecs.ServicesStack services_stack: root stack for services.
    :param resource: The XStack resource
    :return:
    """
    composex_key = f"{X_KEY}{module}"
    ecs_function = get_mod_function(f"{module}.{module}_ecs", f"{module}_to_ecs")
    if ecs_function:
        LOG.debug(ecs_function)
        ecs_function(
            settings.compose_content[composex_key],
            services_stack,
            resource,
            settings,
        )


def apply_x_configs_to_ecs(settings, root_stack):
    """
    Function that evaluates only the x- resources of the root template and iterates over the resources.
    If there is an implemented module in ECS ComposeX for that resource to map to the ECS Services, it will
    execute the function available in the module to apply defined settings to the services stack.

    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param ecs_composex.ecs.ServicesStack root_stack: root stack for services.
    """
    for resource_name in root_stack.stack_template.resources:
        resource = root_stack.stack_template.resources[resource_name]
        if (
            issubclass(type(resource), ComposeXStack)
            and resource_name in SUPPORTED_X_MODULE_NAMES
            and not resource.is_void
        ):
            module = getattr(resource, "title")
            invoke_x_to_ecs(module, settings, root_stack, resource)


def apply_x_to_x_configs(root_template, settings):
    """
    Function to iterate over each XStack and trigger cross-x resources configurations functions

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
            and not resource.is_void
        ):
            resource.add_xdependencies(root_template, settings.compose_content)


def add_compute(root_template, settings, vpc_stack):
    """
    Function to add Cluster stack to root one. If any of the options related to compute resources are set in the CLI
    then this function will generate and add the compute template to the root stack template

    :param troposphere.Template root_template: the root template
    :param ComposeXStack vpc_stack: the VPC stack if any to pull the attributes from
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


def handle_new_xstack(
    key,
    res_type,
    settings,
    services_stack,
    vpc_stack,
    root_template,
    xstack,
):
    """
    Function to create the root stack of the x-resource and assign it to its root stack

    :param str key:
    :param str res_type:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.ecs.ServicesStack services_stack:
    :param ecs_composex.common.stacks ComposeXStack vpc_stack:
    :param troposphere.Template root_template:
    :param ecs_composex.common.stacks ComposeXStack xstack:
    """

    LOG.debug(xstack, xstack.is_void)
    if xstack.is_void:
        invoke_x_to_ecs(res_type, settings, services_stack, xstack)
    elif (
        hasattr(xstack, "title")
        and hasattr(xstack, "stack_template")
        and not xstack.is_void
    ):
        root_template.add_resource(xstack)
        if vpc_stack and key in TCP_SERVICES:
            xstack.get_from_vpc_stack(vpc_stack)
        elif not vpc_stack and key in TCP_SERVICES:
            xstack.no_vpc_parameters()


def add_x_resources(root_template, settings, services_stack, vpc_stack=None):
    """
    Function to add each X resource from the compose file
    """
    for key in settings.compose_content:
        if key.startswith(X_KEY) and key not in EXCLUDED_X_KEYS:
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
            handle_new_xstack(
                key,
                res_type,
                settings,
                services_stack,
                vpc_stack,
                root_template,
                xstack,
            )


def create_services(root_stack, settings, vpc_stack, dns_params):
    """
    Function to add the microservices root stack

    :param ComposeXStack root_stack: ComposeX root stack
    :param ComposeXSettings settings: The settings for execution
    :param ComposeXStack vpc_stack: The VPC Stack
    :param dict dns_params: DNS Parameters for the execution
    """
    associate_services_to_root_stack(root_stack, settings, dns_params, vpc_stack)


def get_vpc_id(vpc_stack):
    """
    Function to add CloudMap to VPC

    :param ComposeXStack vpc_stack: VpcStack
    """
    if vpc_stack:
        return GetAtt(VPC_STACK_NAME, f"Outputs.{vpc_params.VPC_ID_T}")
    else:
        return Ref(vpc_params.VPC_ID)


def init_root_template():
    """
    Function to initialize the root template

    :return: template
    :rtype: troposphere.Template
    """

    template = build_template(
        "Root template generated via ECS ComposeX",
        [USE_FLEET, USE_ONDEMAND, CLUSTER_NAME, CREATE_CLUSTER],
    )
    template.add_condition(CREATE_CLUSTER_CON_T, CREATE_CLUSTER_CON)
    return template


def generate_full_template(settings):
    """
    Function to generate the root root_template

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return root_template: Template, params
    :rtype: root_template, list
    """
    LOG.debug(settings)
    root_stack_title = NONALPHANUM.sub("", settings.name.title())
    root_stack = ComposeXStack(
        root_stack_title, stack_template=init_root_template(), file_name=settings.name
    )
    dns_inputs(root_stack)
    vpc_stack = add_vpc_to_root(root_stack, settings)
    dns_settings = DnsSettings(root_stack, settings, get_vpc_id(vpc_stack))
    root_stack.Parameters.update(dns_settings.root_params)
    add_ecs_cluster(settings, root_stack)
    compute_stack = add_compute(root_stack.stack_template, settings, vpc_stack)
    if settings.create_compute and compute_stack:
        compute_stack.DependsOn.append(ROOT_CLUSTER_NAME)
    create_services(root_stack, settings, vpc_stack, dns_settings.nested_params)
    if keyisset(ACM_KEY, settings.compose_content):
        init_acm_certs(settings, dns_settings, root_stack)
    add_x_resources(
        root_stack.stack_template,
        settings,
        root_stack,
        vpc_stack=vpc_stack,
    )
    apply_x_configs_to_ecs(
        settings,
        root_stack,
    )
    apply_x_to_x_configs(root_stack.stack_template, settings)
    if keyisset("x-appmesh", settings.compose_content):
        mesh = Mesh(settings.compose_content["x-appmesh"], root_stack, settings)
        mesh.render_mesh_template(root_stack)
    add_all_tags(root_stack.stack_template, settings)
    return root_stack
