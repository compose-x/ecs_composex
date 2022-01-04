# -*- coding: utf-8 -*-
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
from ecs_composex.acm.acm_stack import XStack as AcmStack
from ecs_composex.alarms.alarms_ecs import set_services_alarms
from ecs_composex.appmesh.appmesh_mesh import Mesh
from ecs_composex.common import LOG, NONALPHANUM, add_parameters, init_template
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import X_AWS_KEY, X_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import add_all_tags
from ecs_composex.compute.compute_stack import ComputeStack
from ecs_composex.dashboards.dashboards_stack import XStack as DashboardsStack
from ecs_composex.dns import DnsSettings
from ecs_composex.dns.dns_records import DnsRecords
from ecs_composex.ecs.ecs_cluster import add_ecs_cluster
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.ecs.ecs_stack import associate_services_to_root_stack
from ecs_composex.iam.iam_stack import XStack as IamStack
from ecs_composex.vpc import vpc_params
from ecs_composex.vpc.vpc_stack import XStack as VpcStack

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
    "opensearch",
    "neptune",
]

SUPPORTED_X_MODULES = [f"{X_KEY}{mod_name}" for mod_name in SUPPORTED_X_MODULE_NAMES]
EXCLUDED_X_KEYS = [
    f"{X_KEY}configs",
    f"{X_KEY}tags",
    f"{X_KEY}appmesh",
    # f"{X_KEY}acm"
    f"{X_KEY}vpc",
    f"{X_KEY}dns",
    f"{X_KEY}cluster",
    f"{X_KEY}dashboards",
]
TCP_MODES = [
    "rds",
    "appmesh",
    "elbv2",
    "docdb",
    "elasticache",
    "efs",
    "opensearch",
    "neptune",
]
TCP_SERVICES = [f"{X_KEY}{mode}" for mode in TCP_MODES]

ENV_RESOURCE_MODULES = [
    # "vpc",
    # "dns",
    "acm",
]
ENV_RESOURCES = [f"{X_KEY}{mode}" for mode in ENV_RESOURCE_MODULES]


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


def invoke_x_to_ecs(module_name, services_stack, resource, settings):
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


def apply_x_configs_to_ecs(settings, root_stack):
    """
    Function that evaluates only the x- resources of the root template and iterates over the resources.
    If there is an implemented module in ECS ComposeX for that resource_stack to map to the ECS Services, it will
    execute the function available in the module to apply defined settings to the services stack.

    The root_stack is used as the parent stack to the services.

    :param ecs_composex.common.settings.ComposeXSettings settings: The compose file content
    :param ecs_composex.ecs.ServicesStack root_stack: root stack for services.
    """
    for resource_stack in root_stack.stack_template.resources.values():
        if (
            issubclass(type(resource_stack), ComposeXStack)
            and resource_stack.name in SUPPORTED_X_MODULE_NAMES
            # and resource_stack.name not in ENV_RESOURCE_MODULES
            and not resource_stack.is_void
        ):
            invoke_x_to_ecs(None, root_stack, resource_stack, settings)
    for resource_stack in settings.x_resources_void:
        res_type = list(resource_stack.keys())[-1]
        invoke_x_to_ecs(res_type, root_stack, resource_stack[res_type], settings)


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
        compute_stack.set_vpc_parameters_from_vpc_stack(vpc_stack)
    else:
        compute_stack.set_vpc_params_from_vpc_stack_import(vpc_stack)
    return root_template.add_resource(compute_stack)


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
    if xstack.is_void:
        settings.x_resources_void.append({res_type: xstack})
    elif (
        hasattr(xstack, "title")
        and hasattr(xstack, "stack_template")
        and not xstack.is_void
    ):
        root_stack.stack_template.add_resource(xstack)


def add_x_env_resources(root_stack, settings):
    """
    Processes the modules / resources that are defining the environment settings
    """
    for key in settings.compose_content:
        if (
            key.startswith(X_KEY)
            and key in ENV_RESOURCES
            and not re.match(X_AWS_KEY, key)
        ):
            process_x_class(root_stack, settings, key)


def add_x_resources(root_stack, settings):
    """
    Function to add each X resource from the compose file
    """
    for key in settings.compose_content:
        if (
            key.startswith(X_KEY)
            and key not in EXCLUDED_X_KEYS
            and key not in ENV_RESOURCES
            and not re.match(X_AWS_KEY, key)
        ):
            process_x_class(root_stack, settings, key)
            # if vpc_stack and key in TCP_SERVICES:
            #     xstack.get_from_vpc_stack(vpc_stack)
            # elif not vpc_stack and key in TCP_SERVICES:
            #     xstack.no_vpc_stack_parameters(settings)


def get_vpc_id(vpc_stack):
    """
    Function to add CloudMap to VPC

    :param ecs_composex.vpc.vpc_stack.VpcStack vpc_stack: The VPC Stack used in this execution
    """
    if not vpc_stack.is_void and vpc_stack.vpc_resource:
        return GetAtt(VPC_STACK_NAME, f"Outputs.{vpc_params.VPC_ID_T}")
    elif vpc_stack.is_void and vpc_stack.vpc_resource.mappings:
        return FindInMap("Network", vpc_params.VPC_ID.title, vpc_params.VPC_ID.title)


def init_root_template():
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


def set_ecs_cluster_identifier(root_stack, settings):
    """
    Final pass at the top stacks parameters to set the ECS cluster parameter

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for name, resource in root_stack.stack_template.resources.items():
        if issubclass(type(resource), ComposeXStack) and CLUSTER_NAME.title in [
            param.title for param in resource.stack_template.parameters.values()
        ]:
            resource.Parameters.update(
                {CLUSTER_NAME.title: settings.ecs_cluster.cluster_identifier}
            )


def create_root_stack(settings) -> ComposeXStack:
    """
    Initializes the root stack template and ComposeXStack

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    """
    root_stack_title = NONALPHANUM.sub("", settings.name.title())
    root_stack = ComposeXStack(
        root_stack_title,
        stack_template=init_root_template(),
        file_name=settings.name,
    )
    return root_stack


def add_iam_dependency(iam_stack: ComposeXStack, family):
    """
    Adds the IAM Stack as dependency to the family one if not set already

    :param ecs_composex.common.stacks.ComposeXStack iam_stack:
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    """
    if iam_stack.title not in family.stack.DependsOn:
        family.stack.DependsOn.append(iam_stack.title)


def update_families_networking_settings(settings, vpc_stack):
    """
    Function to update the families network settings prior to rendering the ECS Service settings

    :param settings: Runtime Execution setting
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :param vpc_stack: The VPC stack and details
    :type vpc_stack: ecs_composex.vpc.vpc_stack.VpcStack
    """
    for family in settings.families.values():
        if family.launch_type == "EXTERNAL":
            LOG.info(f"{family.name} Ingress cannot be set (EXTERNAL mode). Skipping")
            continue
        if vpc_stack.vpc_resource.mappings:
            family.stack.set_vpc_params_from_vpc_stack_import(vpc_stack)
        else:
            family.stack.set_vpc_parameters_from_vpc_stack(vpc_stack)
        family.add_security_group()
        family.service_config.network.set_aws_sources_ingress(
            settings,
            family.logical_name,
            GetAtt(family.service_config.network.security_group, "GroupId"),
        )
        family.service_config.network.set_ext_sources_ingress(
            family.logical_name,
            GetAtt(family.service_config.network.security_group, "GroupId"),
        )
        family.service_config.network.associate_aws_igress_rules(family.template)
        family.service_config.network.associate_ext_igress_rules(family.template)
        family.service_config.network.add_self_ingress(family)


def update_network_resources_vpc_config(settings, vpc_stack):
    """
    Iterate over the settings.x_resources, over the root stack nested stacks.
    If the nested stack has x_resources that depend on VPC, update the stack parameters with the vpc stack settings

    Although the first if should never be true, setting condition in case for safety.

    :param settings: Runtime Execution setting
    :type settings: ecs_composex.common.settings.ComposeXSettingsngs
    :param vpc_stack: The VPC stack and details
    :type vpc_stack: ecs_composex.vpc.vpc_stack.VpcStack
    """
    for resource in settings.x_resources:
        if resource.mappings:
            LOG.debug(
                f"{resource.module_name}.{resource.name} - Lookup resource need no VPC Settings."
            )
            continue
        if not resource.requires_vpc:
            LOG.debug(
                f"{resource.module_name}.{resource.name} - Resource is not bound to VPC."
            )
            continue
        if (
            resource.stack.parent_stack is None
            or resource.stack == resource.stack.get_top_root_stack()
        ):
            LOG.debug(f"{resource.stack.title} is not a nested stacks")
            if vpc_stack.vpc_resource.mappings:
                resource.stack.set_vpc_params_from_vpc_stack_import(vpc_stack)
            else:
                resource.stack.set_vpc_parameters_from_vpc_stack(vpc_stack)
        if resource.requires_vpc and hasattr(resource, "update_from_vpc"):
            resource.update_from_vpc(vpc_stack, settings)


def set_families_ecs_service(settings):
    """
    Sets the ECS Service in the family.ecs_service from ServiceConfig and family settings
    """
    for family in settings.families.values():
        family.ecs_service.generate_service_definition(family, settings)
        family.service_config.scaling.create_scalable_target(family)
        # family.ecs_service.generate_service_template_outputs(family)


def handle_vpc_settings(settings, vpc_stack, root_stack):
    """
    Function to deal with vpc stack settings

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :param ecs_composex.vpc.vpc_stack.VpcStack vpc_stack: The VPC stack and details
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    """
    if settings.requires_vpc() and not vpc_stack.vpc_resource:
        LOG.info(
            f"{settings.name} - Services or x-Resources need a VPC to function. Creating default one"
        )
        vpc_stack.create_new_vpc("vpc", settings)
        root_stack.stack_template.add_resource(vpc_stack)
    elif (
        vpc_stack.is_void and vpc_stack.vpc_resource and vpc_stack.vpc_resource.mappings
    ):
        root_stack.stack_template.add_mapping(
            "Network", vpc_stack.vpc_resource.mappings
        )
    elif (
        vpc_stack.vpc_resource
        and vpc_stack.vpc_resource.cfn_resource
        and vpc_stack.title not in root_stack.stack_template.resources.keys()
    ):
        root_stack.stack_template.add_resource(vpc_stack)
        LOG.info(f"{settings.name}.x-vpc - VPC stack added. A new VPC will be created.")


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
    LOG.info(
        f"Service families to process {[family.name for family in settings.families.values()]}"
    )
    evaluate_docker_configs(settings)
    root_stack = create_root_stack(settings)
    add_ecs_cluster(root_stack, settings)
    iam_stack = root_stack.stack_template.add_resource(IamStack("iam", settings))
    add_x_env_resources(root_stack, settings)
    add_x_resources(root_stack, settings)
    apply_x_to_x_configs(root_stack, settings)
    associate_services_to_root_stack(root_stack, settings)
    vpc_stack = VpcStack("vpc", settings)
    handle_vpc_settings(settings, vpc_stack, root_stack)

    if vpc_stack.vpc_resource and (
        vpc_stack.vpc_resource.cfn_resource or vpc_stack.vpc_resource.mappings
    ):
        settings.set_networks(vpc_stack)
        dns_settings = DnsSettings(root_stack, settings, get_vpc_id(vpc_stack))
        if settings.use_appmesh:
            mesh = Mesh(
                settings.compose_content["x-appmesh"],
                root_stack,
                settings,
                dns_settings,
            )
            mesh.render_mesh_template(root_stack, settings, dns_settings)

    update_families_networking_settings(settings, vpc_stack)
    update_network_resources_vpc_config(settings, vpc_stack)
    set_families_ecs_service(settings)

    # set_services_alarms(settings)
    apply_x_configs_to_ecs(
        settings,
        root_stack,
    )
    # dns_records = DnsRecords(settings)
    # dns_records.associate_records_to_resources(settings, root_stack, dns_settings)
    # dns_settings.associate_settings_to_nested_stacks(root_stack)
    # if keyisset("x-dashboards", settings.compose_content):
    #     DashboardsStack("dashboards", settings)
    for family in settings.families.values():
        add_iam_dependency(iam_stack, family)
        family.validate_compute_configuration_for_task(settings)
        family.set_enable_execute_command()
        if family.enable_execute_command:
            family.apply_ecs_execute_command_permissions(settings)
        family.finalize_family_settings()
        family.set_service_dependency_on_all_iam_policies()
        family.state_facts()
    set_ecs_cluster_identifier(root_stack, settings)
    add_all_tags(root_stack.stack_template, settings)
    return root_stack
