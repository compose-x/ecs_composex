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
Module to generate a full stack with VPC, Cluster, Compute, Services and all X- AWS resources.
"""

import re
from importlib import import_module

import boto3
from troposphere import Ref, GetAtt, If
from troposphere.ecs import Cluster

from ecs_composex.common import (
    LOG,
    add_parameters,
    validate_kwargs,
    build_parameters_file,
    build_default_stack_parameters,
)
from ecs_composex.common import build_template, KEYISSET, load_composex_file
from ecs_composex.common import validate_resource_title
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T,
    USE_FLEET,
    USE_FLEET_T,
    USE_ONDEMAND,
    USE_ONDEMAND_T,
)
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common.files import FileArtifact
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import generate_tags_parameters, add_object_tags
from ecs_composex.compute import create_compute_stack
from ecs_composex.compute.compute_params import (
    TARGET_CAPACITY_T,
    TARGET_CAPACITY,
    MIN_CAPACITY_T,
)
from ecs_composex.ecs import ServicesStack
from ecs_composex.ecs import ecs_params, create_services_templates
from ecs_composex.ecs.ecs_conditions import (
    GENERATED_CLUSTER_NAME_CON_T,
    GENERATED_CLUSTER_NAME_CON,
    CLUSTER_NAME_CON_T,
    CLUSTER_NAME_CON,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T, CLUSTER_NAME
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

SUPPORTED_X_MODULES = ["x-rds", "rds", "x-sqs", "sqs"]


def get_composex_globals(compose_content):
    """Parses configs and looks for globals
    :param compose_content: the docker composeX content
    :type compose_content: dict

    :return: docker compose globals
    :rtype: dict
    """
    if KEYISSET("configs", compose_content) and KEYISSET(
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
    :param module_name:
    :return:
    """
    composex_module_name = f"ecs_composex.{module_name}"
    LOG.debug(composex_module_name)
    res_module = None
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
    """Function to create the policies for the resources of a given type

    :param resources: resources to go over from docker ComposeX file
    :type resources: dict
    :param resource_type: resource type, ie. sqs
    :type resource_type: str
    :param function: the function to call to get IAM policies to add to service role
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

        if KEYISSET("Services", resource):
            mod_policies[resource_name] = function(resource_name, resource, **kwargs)
    return mod_policies


def generate_x_resources_envvars(resources, resource_type, function, **kwargs):
    """Function to create the env vars for the resources of given type

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

        if KEYISSET("Services", resource):
            mod_envvars[resource_name] = function(resource_name, resource, **kwargs)
    return mod_envvars


def apply_x_configs_to_ecs(content, root_template, services_stack, **kwargs):
    """
    Function that evaluates only the x- sections of the Compose file
    and generates calls the init function for each.

    :param content: docker ComposeX file content
    :param kwargs: settings for building X related resources

    :return: resource_configs
    :rtype: dict
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
                ecs_function(content[composex_key], services_stack, resource)


def generate_vpc_parameters(template, params, **kwargs):
    """
    Function to add the VPC arguments to the root stack

    :param template: the root template to add the parameters to
    :type template: troposphere.Template
    :param params: list of parameters
    :type params: list
    """
    for arg in VPC_ARGS:
        if KEYISSET(arg, kwargs):
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
    if tags_params is None:
        tags_params = ()
    vpc_template = create_vpc_template(session=session, **kwargs)
    parameters = {ROOT_STACK_NAME_T: Ref("AWS::StackName")}
    for param in tags_params:
        parameters.update({param.title: Ref(param.title)})
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
        if KEYISSET(arg, kwargs):
            create_compute = True
    if not create_compute:
        return
    if params is None:
        params = []
    if tags is None:
        tags = ()
    depends_on = []
    root_template.add_parameter(TARGET_CAPACITY)
    compute_template = create_compute_stack(session, **kwargs)
    parameters = {
        ROOT_STACK_NAME_T: Ref("AWS::StackName"),
        TARGET_CAPACITY_T: Ref(TARGET_CAPACITY),
        MIN_CAPACITY_T: Ref(TARGET_CAPACITY),
        USE_FLEET_T: Ref(USE_FLEET),
        USE_ONDEMAND_T: Ref(USE_ONDEMAND),
    }
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
            template=compute_template[0],
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
    ignore_x = ["x-tags"]
    # iam_services = ["x-sqs"]
    tcp_services = ["x-rds"]
    depends_on = []
    if tags is None:
        tags = []
    for key in content:
        if key.startswith("x-") and key not in ignore_x:
            res_type = RES_REGX.sub("", key)
            function_name = f"create_{res_type}_template"
            xclass = get_mod_class(res_type)
            create_function = get_mod_function(res_type, function_name)
            if create_function:
                x_template = create_function(session=session, **kwargs)
                if vpc_stack is not None and key in tcp_services:
                    depends_on.append(VPC_STACK_NAME)
                parameters = {ROOT_STACK_NAME_T: Ref("AWS::StackName")}
                for tag in tags:
                    parameters.update({tag.title: Ref(tag.title)})
                LOG.debug(xclass)
                xstack = xclass(
                    res_type.strip(),
                    template=x_template,
                    Parameters=parameters,
                    DependsOn=depends_on,
                    **kwargs,
                )
                if vpc_stack and key in tcp_services:
                    xstack.add_vpc_stack(vpc_stack)
                template.add_resource(xstack)


def add_services(template, depends, session, vpc_stack=None, **kwargs):
    """
    Function to add the microservices root stack
    :param template: root template
    :type template: troposphere.Template
    :param depends: list of dependencies for the stack
    :type depends: list
    :param session: ovveride boto session for API calls
    :type session: boto3.session.Session
    :param vpc_stack: the VPC Stack
    :type vpc_stack: troposphere.cloudformation.Template
    :param kwargs: optional parameters
    """
    services_template = create_services_templates(session=session, **kwargs)
    stack = ServicesStack(
        "Services", template=services_template, DependsOn=depends, **kwargs
    )
    if KEYISSET("CreateCluster", kwargs):
        stack.add_cluster_parameter({ecs_params.CLUSTER_NAME_T: Ref(ROOT_CLUSTER_NAME)})
    else:
        stack.add_cluster_parameter({ecs_params.CLUSTER_NAME_T: Ref(CLUSTER_NAME)})
    if vpc_stack:
        stack.add_vpc_stack(vpc_stack)
    return template.add_resource(stack)


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
    Cluster(
        ROOT_CLUSTER_NAME,
        template=template,
        ClusterName=If(CLUSTER_NAME_CON_T, Ref("AWS::StackName"), Ref(CLUSTER_NAME_T)),
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
        [USE_FLEET, USE_ONDEMAND, CLUSTER_NAME],
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
    stack_params = []
    build_default_stack_parameters(stack_params, **kwargs)
    kwargs.update(get_composex_globals(content))
    tags_params = generate_tags_parameters(content)
    template = init_root_template(stack_params, tags_params)
    LOG.debug(kwargs)
    validate_kwargs(["BucketName"], kwargs)
    vpc_stack = None
    depends_on = []
    services_stack = add_services(
        template, depends_on, session=session, vpc_stack=vpc_stack, **kwargs
    )
    if KEYISSET("CreateVpc", kwargs):
        vpc_stack = add_vpc_to_root(template, session, tags_params[0], **kwargs)
        depends_on.append(vpc_stack)
        add_object_tags(vpc_stack, tags_params[1])
        services_stack.add_vpc_stack(vpc_stack)
    else:
        generate_vpc_parameters(template, stack_params, **kwargs)
        LOG.debug(stack_params)
    if KEYISSET(CLUSTER_NAME_T, kwargs):
        build_parameters_file(stack_params, CLUSTER_NAME_T, kwargs[CLUSTER_NAME_T])
    if KEYISSET("CreateCluster", kwargs):
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
    apply_x_configs_to_ecs(content, template, services_stack, **kwargs)
    for resource in template.resources:
        add_object_tags(template.resources[resource], tags_params[1])
    return template, stack_params
