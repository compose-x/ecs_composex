#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Main module to generate a full stack with VPC, Cluster, Compute, Services and all X- AWS resources.
"""

import re
import warnings
from importlib import import_module

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_STACK_NAME, FindInMap, GetAtt, Ref

from ecs_composex.acm.acm_params import RES_KEY as ACM_KEY
from ecs_composex.acm.acm_stack import init_acm_certs
from ecs_composex.alarms.alarms_ecs import set_services_alarms
from ecs_composex.appmesh.appmesh_mesh import Mesh
from ecs_composex.common import LOG, NONALPHANUM, init_template
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import X_AWS_KEY, X_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import add_all_tags
from ecs_composex.compute.compute_stack import ComputeStack
from ecs_composex.dashboards.dashboards_stack import XStack as DashboardsStack
from ecs_composex.dns import DnsSettings
from ecs_composex.dns.dns_records import DnsRecords
from ecs_composex.ecs.ecs_cluster import add_ecs_cluster
from ecs_composex.ecs.ecs_stack import associate_services_to_root_stack
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_stack import add_vpc_to_root

try:
    from ecs_composex.ecr.ecr_scans_eval import (
        define_service_image,
        interpolate_ecr_uri_tag_with_digest,
        invalidate_image_from_ecr,
        scan_service_image,
    )

    SCANS_POSSIBLE = True
except ImportError:
    warnings.warn(
        "You must install ecs-composex[ecrscan] extra to use this functionality"
    )
    SCANS_POSSIBLE = False

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
    "events",
    "kinesis",
    "elasticache",
    "efs",
    "alarms",
    "codeguru_profiler",
    "ssm_parameter",
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
    f"{X_KEY}dashboards",
]
TCP_MODES = ["rds", "appmesh", "elbv2", "docdb", "elasticache", "efs"]
TCP_SERVICES = [f"{X_KEY}{mode}" for mode in TCP_MODES]


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


def invoke_x_to_ecs(module_name, settings, services_stack, resource):
    """
    Function to associate X resources to Services

    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param ecs_composex.ecs.ServicesStack services_stack: root stack for services.
    :param resource: The XStack resource
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
            and resource.name in SUPPORTED_X_MODULE_NAMES
            and not resource.is_void
        ):
            invoke_x_to_ecs(None, settings, root_stack, resource)


def apply_x_to_x_configs(root_stack, settings):
    """
    Function to iterate over each XStack and trigger cross-x resources configurations functions

    :param ComposeXStack root_stack: the ECS ComposeX root template
    :param ComposeXSettings settings: The execution settings
    :return:
    """
    for resource_name, resource in root_stack.stack_template.resources.items():
        if (
            issubclass(type(resource), ComposeXStack)
            and resource.name in SUPPORTED_X_MODULE_NAMES
            and hasattr(resource, "add_xdependencies")
            and not resource.is_void
        ):
            resource.add_xdependencies(root_stack, settings)


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
    parameters = {ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME)}
    compute_stack = ComputeStack(
        COMPUTE_STACK_NAME, settings=settings, parameters=parameters
    )
    if isinstance(settings.ecs_cluster, Ref):
        compute_stack.DependsOn.append(settings.ecs_cluster.data["Ref"])
    if vpc_stack is not None:
        compute_stack.get_from_vpc_stack(vpc_stack)
    else:
        compute_stack.no_vpc_parameters(settings)
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
            xstack.no_vpc_parameters(settings)


def add_x_resources(root_template, settings, services_stack, vpc_stack=None):
    """
    Function to add each X resource from the compose file
    """
    for key in settings.compose_content:
        if (
            key.startswith(X_KEY)
            and key not in EXCLUDED_X_KEYS
            and not re.match(X_AWS_KEY, key)
        ):
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


def get_vpc_id(vpc_stack):
    """
    Function to add CloudMap to VPC

    :param ComposeXStack vpc_stack: VpcStack
    """
    if vpc_stack:
        return GetAtt(VPC_STACK_NAME, f"Outputs.{vpc_params.VPC_ID_T}")
    else:
        return FindInMap("Network", vpc_params.VPC_ID.title, vpc_params.VPC_ID.title)


def init_root_template(settings):
    """
    Function to initialize the root template

    :return: template
    :rtype: troposphere.Template
    """
    template = init_template("Root template generated via ECS ComposeX")
    template.add_mapping("ComposeXDefaults", {"ECS": {"PlatformVersion": "1.4.0"}})
    return template


def evaluate_docker_configs(settings):
    """
    Function to go over the services settings and evaluate x-docker

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return:
    """
    image_tag_re = re.compile(r"(?P<tag>(?:\@sha[\d]+:[a-z-Z0-9]+$)|(?::[\S]+$))")
    for family in settings.families.values():
        for service in family.services:
            if not keyisset("x-docker_opts", service.definition):
                continue
            docker_config = service.definition["x-docker_opts"]
            if SCANS_POSSIBLE:
                if keyisset("InterpolateWithDigest", docker_config):
                    if not invalidate_image_from_ecr(service, mute=True):
                        LOG.warn(
                            "You set InterpolateWithDigest to true for x-docker for an image in AWS ECR."
                            "Please refer to x-ecr"
                        )
                        continue
                else:
                    warnings.warn(
                        "Run pip install ecs_composex[ecrscan] to use x-ecr features"
                    )
                service.retrieve_image_digest()
                if service.image_digest:
                    service.image = image_tag_re.sub(
                        f"@{service.image_digest}", service.image
                    )
                    LOG.info(f"Successfully retrieved digest for {service.name}.")
                    LOG.info(f"{service.name} - {service.image}")


def evaluate_ecr_configs(settings):
    """
    Function to go over each service of each family in its final state and evaluate the ECR Image validity.

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return:
    """
    result = 0
    if not SCANS_POSSIBLE:
        return result
    for family in settings.families.values():
        for service in family.services:
            if not keyisset("x-ecr", service.definition) or invalidate_image_from_ecr(
                service, True
            ):
                continue
            service_image = define_service_image(service, settings)
            if (
                service.ecr_config
                and keyisset("InterpolateWithDigest", service.ecr_config)
                and keyisset("imageDigest", service_image)
            ):
                service.image = interpolate_ecr_uri_tag_with_digest(
                    service.image, service_image["imageDigest"]
                )
                LOG.info(
                    f"Update service {family.name}.{service.name} image to {service.image}"
                )
            if scan_service_image(service, settings, service_image):
                LOG.warn(f"{family.name}.{service.name} - vulnerabilities found")
                result = 1
            else:
                LOG.info(f"{family.name}.{service.name} - ECR Evaluation Passed.")
    return result


def generate_full_template(settings):
    """
    Function to generate the root root_template

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return root_template: Template, params
    :rtype: root_template, list
    """
    LOG.debug(settings)
    evaluate_docker_configs(settings)
    root_stack_title = NONALPHANUM.sub("", settings.name.title())
    root_stack = ComposeXStack(
        root_stack_title,
        stack_template=init_root_template(settings),
        file_name=settings.name,
    )
    vpc_stack = add_vpc_to_root(root_stack, settings)
    settings.set_networks(vpc_stack, root_stack)
    dns_settings = DnsSettings(root_stack, settings, get_vpc_id(vpc_stack))
    add_ecs_cluster(root_stack, settings)
    associate_services_to_root_stack(root_stack, settings, vpc_stack)
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
    apply_x_to_x_configs(root_stack, settings)
    if settings.use_appmesh:
        mesh = Mesh(
            settings.compose_content["x-appmesh"],
            root_stack,
            settings,
            dns_settings,
        )
        mesh.render_mesh_template(root_stack, settings, dns_settings)
    dns_records = DnsRecords(settings)
    dns_records.associate_records_to_resources(settings, root_stack, dns_settings)
    dns_settings.associate_settings_to_nested_stacks(root_stack)
    set_services_alarms(settings)
    if keyisset("x-dashboards", settings.compose_content):
        DashboardsStack("dashboards", settings)
    add_all_tags(root_stack.stack_template, settings)
    for family in settings.families.values():
        family.validate_compute_configuration_for_task(settings)
    return root_stack
