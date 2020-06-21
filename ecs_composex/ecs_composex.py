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

import boto3
from troposphere import Ref, GetAtt, If, AWS_STACK_NAME
from troposphere.ecs import Cluster

from ecs_composex.common import (
    LOG,
    add_parameters,
    validate_kwargs,
    build_parameters_file,
    build_default_stack_parameters,
)
from ecs_composex.common import (
    build_template,
    keyisset,
    load_composex_file,
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
from ecs_composex.common.aws import get_curated_azs
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import generate_tags_parameters, add_all_tags
from ecs_composex.compute import create_compute_stack
from ecs_composex.compute.compute_params import (
    TARGET_CAPACITY_T,
    TARGET_CAPACITY,
    MIN_CAPACITY_T,
)
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
from ecs_composex.vpc import create_vpc_template
from ecs_composex.vpc import vpc_params

RES_REGX = re.compile(r"(^([x-]+))")
ROOT_CLUSTER_NAME = "EcsCluster"
COMPUTE_STACK_NAME = "Ec2Compute"
VPC_STACK_NAME = "vpc"

VPC_ARGS = [
    vpc_params.PUBLIC_SUBNETS_T,
    vpc_params.APP_SUBNETS_T,
    vpc_params.STORAGE_SUBNETS_T,
    vpc_params.VPC_ID_T,
    vpc_params.VPC_MAP_ID_T,
]

SUPPORTED_X_MODULES = ["x-rds", "rds", "x-sqs", "sqs", "x-sns", "sns"]
EXCLUDED_X_KEYS = ["x-configs", "x-tags"]


def get_composex_globals(compose_content):
    """
    Parses configs and looks for composex

    :param compose_content: the docker composeX content
    :type compose_content: dict

    :return: docker compose globals
    :rtype: dict
    """
    if keyisset("configs", compose_content) and keyisset(
        "composex", compose_content["configs"]
    ):
        return compose_content["configs"]["composex"]
    return {}


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
    res_module = None
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
    composex_module_name = f"ecs_composex.{module_name}"
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


def generate_x_resources_envvars(resources, resource_type, function, **kwargs):
    """
    Function to create the env vars for the resources of given type

    :param resources: resources to go over for generating envvars
    :type resources: dict
    :param resource_type: resource type, i.e., sqs
    :type resource_type: str
    :param function: the function to use to fetch the information needed
    :type function: function pointer
    :param kwargs: optional arguments
    :type kwargs: dict

    :return: envvars for resources of the given resource type to be used by microservices for environment variables
    :rtype: dict
    """
    mod_envvars = {}
    for resource_name in resources:
        assert validate_resource_title(resource_name, resource_type)
        resource = resources[resource_name]

        if keyisset("Services", resource):
            mod_envvars[resource_name] = function(resource_name, resource, **kwargs)
    return mod_envvars


def apply_x_configs_to_ecs(
    content, root_template, services_stack, services_families, **kwargs
):
    """
    Function that evaluates only the x- resources of the root template and iterates over the resources.
    If there is an implemented module in ECS ComposeX for that resource to map to the ECS Services, it will
    execute the function available in the module to apply defined settings to the services stack.

    :param dict content: The compose file content
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
                    content[composex_key], services_stack, services_families, resource
                )


def apply_x_to_x_configs(root_template, content):
    """
    Function to iterate over each XResource and trigger cross-x resources configurations functions

    :param troposphere.Template root_template: the ECS ComposeX root template
    :param dict content: The Docker compose file content
    :return:
    """
    for resource_name in root_template.resources:
        resource = root_template.resources[resource_name]
        if (
            issubclass(type(resource), ComposeXStack)
            and resource_name in SUPPORTED_X_MODULES
            and hasattr(resource, "add_xdependencies")
        ):
            resource.add_xdependencies(root_template, content)


def generate_vpc_parameters(template, params, **kwargs):
    """
    Function to add the VPC arguments to the root stack

    :param template: the root template to add the parameters to
    :type template: troposphere.Template
    :param params: list of parameters
    :type params: list
    """
    for arg in VPC_ARGS:
        if keyisset(arg, kwargs):
            build_parameters_file(params, arg, kwargs[arg])
    params = [
        vpc_params.VPC_ID,
        vpc_params.APP_SUBNETS,
        vpc_params.STORAGE_SUBNETS,
        vpc_params.PUBLIC_SUBNETS,
        vpc_params.VPC_MAP_ID,
    ]
    add_parameters(template, params)


def add_vpc_to_root(root_template, session, tags_params=None, **kwargs):
    """
    Function to add VPC stack to the root one.

    :param tags_params: Tags to add to the stack
    :param root_template: root stack template
    :type root_template: troposphere.Template
    :param session: boto session for override
    :type session: boto3.session.Session
    :param kwargs:

    :return: vpc_stack
    :rtype: troposphere.cloudformation.Stack
    """
    vpc_template = create_vpc_template(session=session, tags=tags_params, **kwargs)
    parameters = {
        ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME),
        USE_CLOUDMAP_T: Ref(USE_CLOUDMAP),
    }
    vpc_stack = root_template.add_resource(
        ComposeXStack(VPC_STACK_NAME, vpc_template, Parameters=parameters, **kwargs)
    )
    return vpc_stack


def add_compute(
    root_template,
    dependencies,
    params,
    vpc_stack=None,
    tags=None,
    session=None,
    **kwargs,
):
    """
    Function to add Cluster stack to root one. If any of the options related to compute resources are set in the CLI
    then this function will generate and add the compute template to the root stack template

    :param dependencies: list of dependencies that need created before creating the Compute stack
    :type dependencies: list
    :param root_template: the root template
    :type root_template: troposphere.Template
    :param params: list of parameters
    :param vpc_stack: the VPC stack if any to pull the attributes from
    :param session: override boto3 session
    :param tags: tags to add to the stack
    :type tags: tuple

    :return: compute_stack, the Compute stack
    :rtype: troposphere.cloudformation.Stack
    """
    create_compute = False
    args = [USE_FLEET_T, USE_ONDEMAND_T, "AddComputeResources"]
    for arg in args:
        if keyisset(arg, kwargs):
            create_compute = True
    if not create_compute:
        return
    if params is None:
        params = []
    depends_on = []
    root_template.add_parameter(TARGET_CAPACITY)
    compute_template = create_compute_stack(session, **kwargs)
    parameters = {
        ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME),
        TARGET_CAPACITY_T: Ref(TARGET_CAPACITY),
        MIN_CAPACITY_T: Ref(TARGET_CAPACITY),
        USE_FLEET_T: Ref(USE_FLEET),
        USE_ONDEMAND_T: Ref(USE_ONDEMAND),
    }
    if tags:
        for tag in tags[0]:
            parameters.update({tag.title: Ref(tag.title)})
    if vpc_stack is not None:
        depends_on.append(vpc_stack)
        parameters.update(
            {
                vpc_params.VPC_ID_T: GetAtt(
                    vpc_stack, f"Outputs.{vpc_params.VPC_ID_T}"
                ),
                vpc_params.APP_SUBNETS_T: GetAtt(
                    vpc_stack, f"Outputs.{vpc_params.APP_SUBNETS_T}"
                ),
            }
        )
    else:
        # Setup parameters for compute stack without VPC pre-created
        if not kwargs[vpc_params.APP_SUBNETS_T]:
            raise ValueError(
                "No application subnets were provided to create the compute"
            )
        if params is None:
            raise TypeError("params is ", params, "expected", list)
        root_template.add_parameter(vpc_params.APP_SUBNETS)
        parameters.update({vpc_params.APP_SUBNETS_T: Ref(vpc_params.APP_SUBNETS)})
        build_parameters_file(
            params, vpc_params.APP_SUBNETS_T, kwargs[vpc_params.APP_SUBNETS_T]
        )
        params_file = FileArtifact("compute.params.json", content=parameters)
        params_file.create()
    compute_stack = root_template.add_resource(
        ComposeXStack(
            COMPUTE_STACK_NAME,
            stack_template=compute_template[0],
            Parameters=parameters,
            DependsOn=dependencies,
            **kwargs,
        )
    )
    dependencies.append(COMPUTE_STACK_NAME)
    return compute_stack


def add_x_resources(template, session, tags=None, vpc_stack=None, **kwargs):
    """
    Function to add each X resource from the compose file
    """
    content = load_composex_file(kwargs[XFILE_DEST])
    tcp_services = ["x-rds"]
    depends_on = []
    if tags is None:
        tags = []
    for key in content:
        if key.startswith("x-") and key not in EXCLUDED_X_KEYS:
            res_type = RES_REGX.sub("", key)
            function_name = f"create_{res_type}_template"
            xclass = get_mod_class(res_type)
            create_function = get_mod_function(res_type, function_name)
            if create_function:
                x_template = create_function(session=session, **kwargs)
                if vpc_stack is not None and key in tcp_services:
                    depends_on.append(VPC_STACK_NAME)
                parameters = {ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME)}
                for tag in tags:
                    parameters.update({tag.title: Ref(tag.title)})
                LOG.debug(xclass)
                xstack = xclass(
                    res_type.strip(),
                    stack_template=x_template,
                    Parameters=parameters,
                    DependsOn=depends_on,
                    **kwargs,
                )
                if vpc_stack and key in tcp_services:
                    xstack.add_vpc_stack(vpc_stack)
                template.add_resource(xstack)


def add_services(depends, session, vpc_stack=None, **kwargs):
    """
    Function to add the microservices root stack

    :param depends: list of dependencies for the stack
    :type depends: list
    :param session: ovveride boto session for API calls
    :type session: boto3.session.Session
    :param vpc_stack: the VPC Stack
    :type vpc_stack: troposphere.cloudformation.Template
    :param kwargs: optional parameters
    """
    stack = ServicesStack("services", template=None, DependsOn=depends, **kwargs)
    if keyisset("CreateCluster", kwargs):
        stack.add_cluster_parameter({ecs_params.CLUSTER_NAME_T: Ref(ROOT_CLUSTER_NAME)})
    else:
        stack.add_cluster_parameter({ecs_params.CLUSTER_NAME_T: Ref(CLUSTER_NAME)})
    if vpc_stack:
        stack.add_vpc_stack(vpc_stack)
    return stack


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
    # Pending next release to support CapacityProviders in Troposphere
    # When released, will add settings to define cluster capacity
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


def generate_full_template(content, session=None, **kwargs):
    """
    Function to generate the root template

    :param content: ComposeX file content
    :type content: dict
    :param session: boto3 session to override client
    :type session: boto3.session.Session

    :return template: Template, params
    :rtype: template, list
    """
    if session is None:
        session = boto3.session.Session(region_name=kwargs["AwsRegion"])
    if not keyisset("AwsAzs", kwargs):
        kwargs["AwsAzs"] = get_curated_azs(session=session)
    stack_params = []
    build_default_stack_parameters(stack_params, **kwargs)
    kwargs.update(get_composex_globals(content))
    tags_params = generate_tags_parameters(content)
    template = init_root_template(stack_params, tags_params)
    LOG.debug(kwargs)
    validate_kwargs(["BucketName"], kwargs)
    vpc_stack = None
    depends_on = []
    services_families = define_services_families(content[SERVICES_KEY])
    services_stack = template.add_resource(
        add_services(depends_on, session=session, vpc_stack=vpc_stack, **kwargs)
    )
    if keyisset("CreateVpc", kwargs):
        vpc_stack = add_vpc_to_root(template, session, tags_params, **kwargs)
        depends_on.append(vpc_stack)
        services_stack.add_vpc_stack(vpc_stack)
    else:
        generate_vpc_parameters(template, stack_params, **kwargs)
    if keyisset(CLUSTER_NAME_T, kwargs):
        build_parameters_file(stack_params, CLUSTER_NAME_T, kwargs[CLUSTER_NAME_T])
    if keyisset("CreateCluster", kwargs):
        add_ecs_cluster(template, depends_on)
        depends_on.append(ROOT_CLUSTER_NAME)
    add_compute(
        template,
        depends_on,
        stack_params,
        vpc_stack,
        tags=tags_params,
        session=session,
        **kwargs,
    )
    add_x_resources(template, session=session, vpc_stack=vpc_stack, **kwargs)
    apply_x_configs_to_ecs(
        content, template, services_stack, services_families, **kwargs
    )
    apply_x_to_x_configs(template, content)
    add_all_tags(template, tags_params)
    LOG.debug(stack_params)
    return template, stack_params
