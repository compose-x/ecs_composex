#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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
from troposphere import Sub, ImportValue, FindInMap
from troposphere.iam import Policy as IamPolicy

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common.compose_services import extend_container_envvars
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.ecs.ecs_params import TASK_ROLE_T
from ecs_composex.kms.kms_perms import ACCESS_TYPES as KMS_ACCESS_TYPES


def generate_export_strings(res_name, attribute):
    """
    Function to generate the SSM and CFN import/export strings
    Returns the import in a tuple

    :param str res_name: name of the queue as defined in ComposeX File
    :param str|Parameter attribute: The attribute to use in Import Name.

    :returns: ImportValue for CFN
    :rtype: ImportValue
    """
    if isinstance(attribute, str):
        cfn_string = f"${{{ROOT_STACK_NAME_T}}}{DELIM}{res_name}{DELIM}{attribute}"
    elif isinstance(attribute, Parameter):
        cfn_string = (
            f"${{{ROOT_STACK_NAME_T}}}{DELIM}{res_name}{DELIM}{attribute.title}"
        )
    else:
        raise TypeError("Attribute can only be a string or Parameter")

    return ImportValue(Sub(cfn_string))


def generate_resource_permissions(resource_name, policies, attribute, arn=None):
    """
    Function to generate IAM permissions for a given x-resource. Returns the mapping of these for the given resource.

    :param str resource_name: The name of the resource
    :param str,None attribute: the attribute of the resource we are using for Import
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
        policy_doc["Resource"] = (
            generate_export_strings(resource_name, attribute) if not arn else arn
        )
        clean_policy["Statement"].append(policy_doc)
        resource_policies[a_type] = IamPolicy(
            PolicyName=Sub(f"{a_type}{resource_name}${{{ROOT_STACK_NAME_T}}}"),
            PolicyDocument=clean_policy,
        )
    return resource_policies


def add_iam_policy_to_service_task_role_v2(
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
    :param target:
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


def map_service_perms_to_resource(resource, family, services, access_type, arn=None):
    """
    Function to
    :param resource:
    :param family:
    :param services:
    :param str access_type:
    :param arn: The ARN to use for permissions, allows remote override
    :return:
    """
    res_perms = generate_resource_permissions(
        f"AccessTo{resource.logical_name}",
        resource.policies_scaffolds,
        resource.arn_attr,
        arn,
    )
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
    key_arn = FindInMap(mapping_family, resource.logical_name, resource.kms_arn_attr)
    kms_perms = generate_resource_permissions(
        f"{resource.logical_name}KmsKey", KMS_ACCESS_TYPES, None, arn=key_arn
    )
    add_iam_policy_to_service_task_role_v2(
        target[0].template, resource, kms_perms, "EncryptDecrypt", selected_services
    )


def handle_lookup_resource(mapping, mapping_family, resource):
    """
    :param dict mapping:
    :param str mapping_family:
    :param resource: The lookup resource
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
                mapping_family, resource.logical_name, resource.main_attr.title
            )
            resource.generate_resource_envvars(None, arn=main_attr_value)
            map_service_perms_to_resource(
                resource, target[0], selected_services, target[3], arn=arn_attr_value
            )
            if (
                hasattr(resource, "kms_arn_attr")
                and resource.kms_arn_attr
                and keyisset(resource.kms_arn_attr, mapping[resource.logical_name])
            ):
                handle_kms_access(mapping_family, resource, target, selected_services)


def assign_new_resource_to_service(resource):
    """
    Function to assign the new resource to the service/family using it.

    """
    resource.generate_resource_envvars(attribute=resource.main_attr)
    for target in resource.families_targets:
        selected_services = get_selected_services(resource, target)
        if selected_services:
            map_service_perms_to_resource(
                resource, target[0], selected_services, target[3]
            )


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
    assign_new_resource_to_service(xresource)
