#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to handle resource settings definition to containers.
"""

from troposphere import Parameter
from troposphere import Sub, ImportValue, FindInMap, Ref
from troposphere.iam import Policy as IamPolicy

from ecs_composex.common import LOG, keyisset, add_parameters
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.compose_services import extend_container_envvars
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.ecs.ecs_params import TASK_ROLE_T
from ecs_composex.kms.kms_perms import ACCESS_TYPES as KMS_ACCESS_TYPES


def define_attribute(attribute):
    """
    Function to check that we either have a str or a Parameter for attribute

    :param str|Parameter attribute:
    :return: attribute name
    :rtype: str
    """
    if isinstance(attribute, str):
        return attribute
    elif isinstance(attribute, Parameter):
        return attribute.title
    else:
        raise TypeError("Attribute can only be a string or Parameter")


def generate_export_strings(res_name, attribute):
    """
    Function to generate the SSM and CFN import/export strings
    Returns the import in a tuple

    :param str res_name: name of the queue as defined in ComposeX File
    :param str|Parameter attribute: The attribute to use in Import Name.

    :returns: ImportValue for CFN
    :rtype: ImportValue
    """
    cfn_string = (
        f"${{{ROOT_STACK_NAME_T}}}{DELIM}{res_name}{DELIM}{define_attribute(attribute)}"
    )
    return ImportValue(Sub(cfn_string))


def generate_resource_permissions(resource_name, policies, arn):
    """
    Function to generate IAM permissions for a given x-resource. Returns the mapping of these for the given resource.

    :param str resource_name: The name of the resource
    :param dict policies: the policies associated with the x-resource type.
    :param str,AWSHelper arn: The ARN of the resource if already looked up.
    :return: dict of the IAM policies associated with the resource.
    :rtype dict:
    """
    resource_policies = {}
    for a_type in policies:
        clean_policy = {"Version": "2012-10-17", "Statement": []}
        LOG.debug(a_type)
        policy_doc = policies[a_type].copy()
        policy_doc["Sid"] = Sub(f"{a_type}To{resource_name}")
        policy_doc["Resource"] = arn
        clean_policy["Statement"].append(policy_doc)
        resource_policies[a_type] = IamPolicy(
            PolicyName=Sub(f"{a_type}{resource_name}${{{ROOT_STACK_NAME_T}}}"),
            PolicyDocument=clean_policy,
        )
    return resource_policies


def add_iam_policy_to_service_task_role(
    service_template, resource, perms, access_type, services
):
    """
    Function to expand the ECS Task Role policy with the permissions for the resource
    :param troposphere.Template service_template:
    :param resource:
    :param perms:
    :param access_type:
    :param list services:
    :return:
    """
    containers = define_service_containers(service_template)
    policy = perms[access_type]
    task_role = service_template.resources[TASK_ROLE_T]
    task_role.Policies.append(policy)
    for container in containers:
        for service in services:
            if container.Name == service.name:
                LOG.debug(f"Extended env vars for {container.Name} -> {service.name}")
                extend_container_envvars(container, resource.env_vars)


def get_selected_services(resource, target):
    """
    Function to get the selected services

    :param resource: The resource linking to services
    :param target: the service/family target definition
    :return:
    """
    if not target[1] and target[2]:
        selected_services = target[2]
        LOG.debug(
            f"Resource {resource.name} only applies to {target[2]} in family {target[0].name}"
        )
    elif target[1]:
        selected_services = target[0].services
        LOG.debug(f"Resource {resource.name} applies to family {target[0].name}")
    else:
        selected_services = []
    return selected_services


def map_service_perms_to_resource(resource, family, services, access_type, value, arn):
    """
    Function to
    :param resource:
    :param family:
    :param services:
    :param str access_type:
    :param value: The value for main attribute, used for env vars
    :param arn: The ARN to use for permissions, allows remote override
    :return:
    """
    res_perms = generate_resource_permissions(
        resource.logical_name,
        resource.policies_scaffolds,
        arn=arn,
    )
    resource.generate_resource_envvars(value)
    containers = define_service_containers(family.template)
    policy = res_perms[access_type]
    task_role = family.template.resources[TASK_ROLE_T]
    task_role.Policies.append(policy)
    for container in containers:
        for service in services:
            if container.Name == service.name:
                LOG.debug(f"Extended env vars for {container.Name} -> {service.name}")
                extend_container_envvars(container, resource.env_vars)


def handle_kms_access(mapping_family, resource, target, selected_services):
    """
    Function to map KMS permissions for the services which need access to a resource using a KMS Key
    :param str mapping_family:
    :param resource:
    :param tuple target:
    :param list selected_services:
    """
    key_arn = FindInMap(
        mapping_family, resource.logical_name, resource.kms_arn_attr.title
    )
    kms_perms = generate_resource_permissions(
        f"{resource.logical_name}KmsKey", KMS_ACCESS_TYPES, arn=key_arn
    )
    add_iam_policy_to_service_task_role(
        target[0].template, resource, kms_perms, "EncryptDecrypt", selected_services
    )


def handle_lookup_resource(mapping, mapping_family, resource):
    """
    :param dict mapping:
    :param str mapping_family:
    :param resource: The lookup resource
    :type resource: ecs_composex.common.compose_resources.XResource
    :return:
    """
    if not keyisset(resource.logical_name, mapping):
        LOG.error(f"No mapping existing for {resource.name}. Skipping")
        return

    for target in resource.families_targets:
        selected_services = get_selected_services(resource, target)
        if selected_services:
            target[0].template.add_mapping(mapping_family, mapping)
            arn_attr_value = FindInMap(
                mapping_family, resource.logical_name, resource.arn_attr.title
            )
            main_attr_value = FindInMap(
                mapping_family, resource.logical_name, resource.ref_parameter.title
            )
            resource.generate_resource_envvars(main_attr_value)
            map_service_perms_to_resource(
                resource,
                target[0],
                selected_services,
                target[3],
                arn=arn_attr_value,
                value=main_attr_value,
            )
            if (
                hasattr(resource, "kms_arn_attr")
                and resource.kms_arn_attr
                and keyisset(
                    resource.kms_arn_attr.title, mapping[resource.logical_name]
                )
            ):
                handle_kms_access(mapping_family, resource, target, selected_services)


def assign_new_resource_to_service(resource, res_root_stack):
    """
    Function to assign the new resource to the service/family using it.

    :param resource: The resource
    :type resource: ecs_composex.common.compose_resources.XResource
    :param res_root_stack: The root stack of the resource type
    :type res_root_stack: ecs_composex.common.stacks.ComposeXStack
    """
    resource.set_ref_resource_value(res_root_stack.title)
    resource.set_resource_arn_parameter()
    resource.set_resource_arn(res_root_stack.title)
    for target in resource.families_targets:
        selected_services = get_selected_services(resource, target)
        if selected_services:
            add_parameters(
                target[0].template, [resource.ref_parameter, resource.arn_parameter]
            )
            target[0].stack.Parameters.update(
                {
                    resource.ref_parameter.title: resource.ref_value,
                    resource.arn_parameter.title: resource.arn_value,
                }
            )
            map_service_perms_to_resource(
                resource,
                target[0],
                selected_services,
                target[3],
                value=Ref(resource.ref_parameter),
                arn=Ref(resource.arn_parameter),
            )
            if res_root_stack.title not in target[0].stack.DependsOn:
                target[0].stack.DependsOn.append(res_root_stack.title)


def handle_resource_to_services(
    xresource,
    services_stack,
    res_root_stack,
    settings,
    nested=False,
):
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_resource_to_services(
                s_resources[resource_name],
                services_stack,
                res_root_stack,
                settings,
                nested=True,
            )
    assign_new_resource_to_service(xresource, res_root_stack)
