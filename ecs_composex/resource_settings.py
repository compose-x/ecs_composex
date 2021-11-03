#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to handle resource settings definition to containers.
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import AWSHelperFn, FindInMap, Ref, Sub
from troposphere.iam import Policy as IamPolicy
from troposphere.iam import PolicyType

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.common.compose_resources import get_parameter_settings
from ecs_composex.common.services_helpers import extend_container_envvars
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.kms.kms_params import MOD_KEY as KMS_MOD


def determine_arns(arn, policy_doc, ignore_missing_primary=False):
    """
    Function allowing to detect whether the resource permissions has a defined override for
    resources ARN. This allows to extend the ARN syntax.

    The policy skeleton must have Resource as a list, and contain ${ARN} into it.

    :param str, list, AWSHelperFn arn:
    :param dict policy_doc: The policy document content
    :param bool ignore_missing_primary: Whether the policy should contain ${ARN} at least
    :return: The list or Resource to put in to the IAM policy
    """
    resources = []
    base_arn = r"${ARN}"
    if keyisset("Resource", policy_doc):
        if base_arn not in policy_doc["Resource"] and not ignore_missing_primary:
            raise KeyError(
                f"The policy skeletion must contain at least {base_arn} when Resource is defined"
            )
        if issubclass(type(arn), AWSHelperFn):
            for resource in policy_doc["Resource"]:
                if not resource.startswith(base_arn):
                    raise ValueError(
                        f"The value {resource} is invalid. It must start with {base_arn}"
                    )
                if resource == base_arn:
                    resources.append(arn)
                else:
                    resources.append(Sub(f"{resource}", ARN=arn))
        return resources
    elif not isinstance(arn, list):
        return [arn]
    else:
        return arn


def generate_resource_permissions(
    resource_name, policies, arn, ignore_missing_primary=False
):
    """
    Function to generate IAM permissions for a given x-resource. Returns the mapping of these for the given resource.
    Suffix takes the values and reduces to the first 118 characters to ensure policy length is below 128
    Short prefix ensures the uniqueness of the policy name but allows to be a constant throughout the life
    of the CFN Stack. It is 8 chars long, leaving a 2 chars margin

    :param str resource_name: The name of the resource
    :param dict policies: the policies associated with the x-resource type.
    :param str,AWSHelper arn: The ARN of the resource if already looked up.
    :param bool ignore_missing_primary: Whether the policy should contain ${ARN} at least
    :return: dict of the IAM policies associated with the resource.
    :rtype dict:
    """
    resource_policies = {}
    for a_type in policies:
        clean_policy = {"Version": "2012-10-17", "Statement": []}
        LOG.debug(a_type)
        policy_doc = policies[a_type].copy()
        resources = determine_arns(arn, policy_doc, ignore_missing_primary)
        policy_doc["Sid"] = f"{a_type}To{resource_name}"
        policy_doc["Resource"] = resources
        clean_policy["Statement"].append(policy_doc)
        suffix = f"{a_type}{resource_name}"[:(118)]
        resource_policies[a_type] = IamPolicy(
            PolicyName=Sub(f"${{ID}}{suffix}", ID=STACK_ID_SHORT),
            PolicyDocument=clean_policy,
        )
    return resource_policies


def generate_resource_permissions_statements(
    resource_name, policies, arn, ignore_missing_primary=False
):
    """
    Function to generate IAM permissions for a given x-resource. Returns the mapping of these for the given resource.
    Suffix takes the values and reduces to the first 118 characters to ensure policy length is below 128
    Short prefix ensures the uniqueness of the policy name but allows to be a constant throughout the life
    of the CFN Stack. It is 8 chars long, leaving a 2 chars margin

    :param str resource_name: The name of the resource
    :param dict policies: the policies associated with the x-resource type.
    :param str,AWSHelper arn: The ARN of the resource if already looked up.
    :param bool ignore_missing_primary: Whether the policy should contain ${ARN} at least
    :return: dict of the IAM policies associated with the resource.
    :rtype dict:
    """
    resource_policies = {}
    for a_type in policies:
        LOG.debug(a_type)
        policy_doc = policies[a_type].copy()
        resources = determine_arns(arn, policy_doc, ignore_missing_primary)
        policy_doc["Sid"] = f"{a_type}To{resource_name}"
        policy_doc["Resource"] = resources
        resource_policies[a_type] = policy_doc
    return resource_policies


def add_iam_policy_to_service_task_role(family, resource, perms, access_type, services):
    """
    Function to expand the ECS Task Role policy with the permissions for the resource
    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param resource:
    :param perms:
    :param access_type:
    :param list services:
    :return:
    """
    containers = define_service_containers(family.template)
    policy = perms[access_type]
    policy_title = f"{family.logical_name}{access_type}To{resource.mapping_key}{resource.logical_name}"
    if policy_title not in family.template.resources:
        res_policy = PolicyType(
            policy_title,
            PolicyName=policy.PolicyName,
            PolicyDocument=policy.PolicyDocument,
            Roles=[Ref(family.task_role.name["ImportParameter"])],
        )
        family.template.add_resource(res_policy)
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


def map_service_perms_to_resource(
    resource, family, services, access_type, arn_value, attributes=None
):
    """
    Function to
    :param resource:
    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param services:
    :param str access_type:
    :param value: The value for main attribute, used for env vars
    :param arn: The ARN to use for permissions, allows remote override
    :return:
    """
    if attributes is None:
        attributes = []
    res_perms = generate_resource_permissions(
        resource.logical_name,
        resource.policies_scaffolds,
        arn=arn_value,
    )
    resource.generate_resource_envvars()
    containers = define_service_containers(family.template)
    policy = res_perms[access_type]
    policy_title = (
        f"{family.logical_name}To{resource.mapping_key}{resource.logical_name}"
    )
    if policy_title not in family.template.resources:
        res_policy = PolicyType(
            policy_title,
            PolicyName=policy.PolicyName,
            PolicyDocument=policy.PolicyDocument,
            Roles=[Ref(family.task_role.name["ImportParameter"])],
        )
        family.template.add_resource(res_policy)
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
        f"{resource.logical_name}KmsKey", get_access_types(KMS_MOD), arn=key_arn
    )
    add_iam_policy_to_service_task_role(
        target[0].template,
        resource,
        kms_perms,
        "EncryptDecrypt",
        selected_services,
    )


def handle_lookup_resource(
    mapping, mapping_family, resource, arn_parameter, parameters=None
):
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
    if parameters is None:
        parameters = []

    if not hasattr(resource, "init_outputs"):
        raise AttributeError(f"Not init_outputs defined for {resource.module_name}")
    resource.init_outputs()
    resource.generate_outputs()

    for target in resource.families_targets:
        selected_services = get_selected_services(resource, target)
        if selected_services:
            target[0].template.add_mapping(mapping_family, mapping)
            arn_attr_value = resource.attributes_outputs[arn_parameter]["ImportValue"]
            resource.generate_resource_envvars()
            map_service_perms_to_resource(
                resource,
                target[0],
                selected_services,
                target[3],
                arn_value=arn_attr_value,
            )
            if (
                hasattr(resource, "kms_arn_attr")
                and resource.kms_arn_attr
                and keyisset(
                    resource.kms_arn_attr.title, mapping[resource.logical_name]
                )
            ):
                handle_kms_access(mapping_family, resource, target, selected_services)


def assign_new_resource_to_service(
    resource, res_root_stack, arn_parameter, parameters=None
):
    """
    Function to assign the new resource to the service/family using it.

    :param resource: The resource
    :type resource: ecs_composex.common.compose_resources.XResource
    :param res_root_stack: The root stack of the resource type
    :type res_root_stack: ecs_composex.common.stacks.ComposeXStack
    :param: The parameter mapping to the ARN attribute of the resource
    :type arn_parameter: ecs_composex.common.cfn_parameter.Parameter arn_parameter
    """
    if parameters is None:
        parameters = []
    arn_settings = get_parameter_settings(resource, arn_parameter)
    extra_settings = [get_parameter_settings(resource, param) for param in parameters]
    params_to_add = [arn_settings[1]]
    params_values = {arn_settings[0]: arn_settings[2]}
    for setting in extra_settings:
        params_to_add.append(setting[1])
        params_values[setting[0]] = setting[2]
    for target in resource.families_targets:
        selected_services = get_selected_services(resource, target)
        if selected_services:
            add_parameters(target[0].template, params_to_add)
            target[0].stack.Parameters.update(params_values)
            map_service_perms_to_resource(
                resource,
                target[0],
                selected_services,
                target[3],
                arn_value=Ref(arn_settings[1]),
                attributes=parameters,
            )
            if res_root_stack.title not in target[0].stack.DependsOn:
                target[0].stack.DependsOn.append(res_root_stack.title)


def handle_resource_to_services(
    xresource,
    services_stack,
    res_root_stack,
    settings,
    arn_parameter,
    parameters=None,
    nested=False,
):
    """
    Function to evaluate the type of resource coming in and pass on the settings and parameters for
    IAM and otherwise assignment

    :param ecs_composex.common.compose_resource.XResource xresource:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param arn_parameter:
    :param bool nested:
    :param list parameters:
    :return:
    """
    if not parameters:
        parameters = []
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_resource_to_services(
                s_resources[resource_name],
                services_stack,
                res_root_stack,
                settings,
                arn_parameter,
                parameters,
                nested=True,
            )
    assign_new_resource_to_service(xresource, res_root_stack, arn_parameter, parameters)
