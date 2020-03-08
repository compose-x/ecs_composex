# -*- coding: utf-8 -*-
"""Main module that allows expansion of ECS ComposeX to add new packages to
support more AWS resources, such as SQS, SNS, RDS etc.

Every package must have a module named {resource_key}_perms so that functions
that return policies and other attributes can find these and execute so the
services can add the policies and environment variable to the task definition
and IAM task role.
"""

import re
from importlib import import_module
from ecs_composex.common import KEYISSET, validate_resource_title, LOG

RES_REGX = re.compile(r"(^([x-]+))")


def get_composex_globals(compose_content):
    """Parses configs and looks for globals
    :param compose_content: the docker composeX content
    :type compose_content: dict

    :return: docker compose globals
    :rtype: dict
    """
    if KEYISSET('configs', compose_content) and KEYISSET('composex', compose_content['configs']):
        return compose_content['configs']['composex']
    return {}


def get_mod_function(module_name, function_name):
    """Gets the permissions function from module

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
    try:
        res_module = import_module(composex_module_name)
        LOG.debug(res_module)
        try:
            function = getattr(res_module, function_name)
            return function
        except AttributeError:
            LOG.info(f"No {function_name} function found - skipping")
    except ImportError as error:
        LOG.error(
            f'Failure to process the module {composex_module_name}'
        )
        LOG.error(error)
    return res_module


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

        if KEYISSET('Services', resource):
            mod_policies[resource_name] = function(
                resource_name, resource, **kwargs
            )
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

        if KEYISSET('Services', resource):
            mod_envvars[resource_name] = function(
                resource_name, resource, **kwargs
            )
    return mod_envvars


def generate_x_resource_configs(content, **kwargs):
    """
    Function that evaluates only the x- sections of the Compose file
    and generates calls the init function for each.

    :param content: docker ComposeX file content
    :param kwargs: settings for building X related resources

    :return: resource_configs
    :rtype: dict
    """
    resource_configs = {}
    options = get_composex_globals(content)
    kwargs.update(options)
    for resource_type in content.keys():
        res_name = RES_REGX.sub('', resource_type)
        resources = content[resource_type]
        if (resource_type.startswith('x-')
                and not (resource_type == 'x-rds' or resource_type == 'x-cluster')
                and content[resource_type]):
            resource_configs[resource_type] = {}
            module_name = f"{res_name}.{res_name}_perms"
            perms_function_name = f"generate_{res_name}_permissions"
            vars_function_name = f"generate_{res_name}_envvars"
            perms_function = get_mod_function(module_name, perms_function_name)
            vars_function = get_mod_function(module_name, vars_function_name)
            LOG.debug(perms_function)
            LOG.debug(vars_function)
            if perms_function:
                resource_configs[resource_type]['permissions'] = generate_x_resources_policies(
                    resources,
                    resource_type,
                    perms_function,
                    **kwargs
                )
            if vars_function:
                resource_configs[resource_type]['envvars'] = generate_x_resources_envvars(
                    resources,
                    resource_type,
                    vars_function,
                    **kwargs
                )
    return resource_configs
