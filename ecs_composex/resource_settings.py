#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle resource settings definition to containers.
"""
import re
from copy import deepcopy

from compose_x_common.compose_x_common import keyisset
from troposphere import AWSHelperFn, FindInMap, Ref, Sub
from troposphere.iam import Policy as IamPolicy
from troposphere.iam import PolicyType

from ecs_composex.common import LOG, add_parameters, add_update_mapping
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.common.services_helpers import extend_container_envvars
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import get_parameter_settings
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.kms.kms_params import MAPPINGS_KEY as KMS_MAPPING_KEY
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
    :rtype: list
    """
    resources = []
    base_arn = r"${ARN}"
    base_arn_re = re.compile(r"^\${ARN}.*$")
    if not keyisset("Resource", policy_doc):
        raise KeyError("Resource not present in policy", policy_doc, arn)
    found_from_regexp = [
        base_arn_re.match(res_string) for res_string in policy_doc["Resource"]
    ]
    if keyisset("Resource", policy_doc):
        if (
            base_arn not in policy_doc["Resource"] and not found_from_regexp
        ) and not ignore_missing_primary:
            raise KeyError(
                f"The policy skeleton must contain at least {base_arn} when Resource is defined",
                "got",
                found_from_regexp,
                "in",
                policy_doc["Resource"],
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
            PolicyName=Sub(f"${{ID}}-{suffix}", ID=STACK_ID_SHORT),
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
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
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
            Roles=[family.task_role.name],
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


def get_access_type_policy_model(
    access_type, policies_models, access_subkey: str = None
):
    """

    :param str|dict access_type:
    :param dict policies_models:
    :param ecs_composex.compose.x_resources.XResource resource:
    :param str access_subkey:
    :return:
    """
    if isinstance(access_type, str):
        return policies_models[access_type]

    elif isinstance(access_type, dict):
        if isinstance(access_type[access_subkey], bool):
            return policies_models[access_subkey]
        else:
            return policies_models[access_type[access_subkey]]


def set_sid_name(access_definition, access_subkey: str) -> str:
    """
    Defines the name of the SID to use for the policy. Defines access_type

    :param dict,str access_definition:
    :param str access_subkey:
    :return: access_type
    :rtype: str
    """
    if isinstance(access_definition, dict) and keyisset(
        access_subkey, access_definition
    ):
        if isinstance(access_definition[access_subkey], bool):
            access_type = access_subkey
        else:
            access_type = f"{access_subkey}{access_definition[access_subkey]}"
    elif isinstance(access_definition, str):
        access_type = access_definition
    else:
        raise ValueError(
            "The access_definition is not valid",
            access_definition,
            type(access_definition),
            "subkey is",
            access_subkey,
        )
    return access_type


def define_iam_permissions(
    resource_mapping_key,
    family,
    policy_title,
    access_type_policy_model,
    access_definition,
    resource_arns,
    access_subkey: str = None,
):
    """
    If a policy already exists to manage resources of the same AWS Service, imports the policy, else, creates one.
    The SID of the policy allows grouping resources that have a similar access pattern together in the same
    statement policy, reducing the policy length (later, might allow for managed policies).
    If there were no SID set already in a statement, adds it.

    :param resource_mapping_key:
    :param family:
    :param str policy_title:
    :param dict access_type_policy_model:
    :param str, dict access_definition:
    :param list resource_arns:
    :param str access_subkey:
    """
    access_type = set_sid_name(access_definition, access_subkey)
    if resource_mapping_key not in family.iam_modules_policies.keys():
        family.iam_modules_policies[resource_mapping_key] = PolicyType(
            policy_title,
            PolicyName=policy_title,
            PolicyDocument={"Version": "2012-10-17", "Statement": []},
            Roles=[family.task_role.name],
        )
        res_policy = family.template.add_resource(
            family.iam_modules_policies[resource_mapping_key]
        )
    else:
        res_policy = family.iam_modules_policies[resource_mapping_key]

    for statement in res_policy.PolicyDocument["Statement"]:
        if keyisset("Sid", statement) and statement["Sid"] == access_type:
            if not isinstance(statement["Resource"], list):
                statement["Resource"] = [statement["Resource"]]
            statement["Resource"] += resource_arns
            return
    access_type_policy_model["Sid"] = access_type
    access_type_policy_model["Resource"] = resource_arns
    res_policy.PolicyDocument["Statement"].append(access_type_policy_model)


def map_service_perms_to_resource(
    family,
    services,
    target,
    arn_value,
    resource=None,
    resource_policies=None,
    resource_mapping_key=None,
    access_definition=None,
    access_subkey=None,
    ignore_missing_primary=False,
):

    if not resource and not resource_policies and not resource_mapping_key:
        raise ValueError(
            "You must specify either resource or resource_policies and resources_mappings"
        )
    resource_policies = resource.policies_scaffolds if resource else resource_policies
    resource_mapping_key = resource.mapping_key if resource else resource_mapping_key
    policies_models = (
        deepcopy(resource_policies)
        if not access_subkey
        else deepcopy(resource_policies[access_subkey])
    )
    access_definition = target[3] if not access_definition else access_definition
    access_type_policy_model = get_access_type_policy_model(
        access_definition, policies_models, access_subkey
    )
    resource_arns = determine_arns(
        arn_value, access_type_policy_model, ignore_missing_primary
    )
    policy_title = f"{family.logical_name}To{resource_mapping_key}"
    define_iam_permissions(
        resource_mapping_key,
        family,
        policy_title,
        access_type_policy_model,
        access_definition,
        resource_arns,
        access_subkey=access_subkey,
    )

    if not resource:
        return
    containers = define_service_containers(family.template)
    for container in containers:
        for service in services:
            if container.Name == service.name:
                LOG.debug(f"Extended env vars for {container.Name} -> {service.name}")
                print(family.name, target[-1])
                if keyisset("ReturnValues", target[-1]):
                    extend_container_envvars(
                        container,
                        resource.generate_resource_service_env_vars(
                            target[-1]["ReturnValues"]
                        ),
                    )
                else:
                    resource.generate_resource_envvars()
                    extend_container_envvars(container, resource.env_vars)


def handle_kms_access(settings, resource, target, selected_services):
    """
    Function to map KMS permissions for the services which need access to a resource using a KMS Key
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.compose_resources.XResource resource: The lookup resource
    :param tuple target:
    :param list selected_services:
    """
    key_arn = resource.attributes_outputs[resource.kms_arn_attr]["ImportValue"]
    map_service_perms_to_resource(
        target[0],
        selected_services,
        target,
        access_definition="EncryptDecrypt",
        arn_value=key_arn,
        resource_policies=get_access_types(KMS_MOD),
        resource_mapping_key=KMS_MAPPING_KEY,
    )


def handle_lookup_resource(settings, resource, arn_parameter, access_subkeys=None):
    """
    Maps resource to designated services for IAM and networking purposes

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.compose_resources.XResource resource: The lookup resource
    :param ecs_composex.common.cfn_params.Parameter arn_parameter:
    :param list access_subkeys:
    """

    for target in resource.families_targets:
        selected_services = get_selected_services(resource, target)
        if selected_services:
            add_update_mapping(
                target[0].template,
                resource.mapping_key,
                settings.mappings[resource.mapping_key],
            )
            arn_attr_value = resource.attributes_outputs[arn_parameter]["ImportValue"]
            if access_subkeys:
                for access_subkey in access_subkeys:
                    if access_subkey not in target[3]:
                        continue
                    map_service_perms_to_resource(
                        target[0],
                        selected_services,
                        target,
                        resource=resource,
                        arn_value=arn_attr_value,
                        access_subkey=access_subkey,
                    )
            else:
                map_service_perms_to_resource(
                    target[0],
                    selected_services,
                    target,
                    resource=resource,
                    arn_value=arn_attr_value,
                    access_subkey=None,
                )
            if (
                hasattr(resource, "kms_arn_attr")
                and resource.kms_arn_attr
                and keyisset(resource.kms_arn_attr, resource.lookup_properties)
            ):
                handle_kms_access(settings, resource, target, selected_services)


def assign_new_resource_to_service(
    resource,
    res_root_stack,
    arn_parameter,
    parameters=None,
    access_subkeys: list = None,
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
            if access_subkeys:
                for access_subkey in access_subkeys:
                    if access_subkey not in target[3]:
                        continue
                    map_service_perms_to_resource(
                        target[0],
                        selected_services,
                        target,
                        arn_value=Ref(arn_settings[1]),
                        resource=resource,
                        access_subkey=access_subkey,
                    )
            else:
                map_service_perms_to_resource(
                    target[0],
                    selected_services,
                    target,
                    resource=resource,
                    arn_value=Ref(arn_settings[1]),
                    access_subkey=None,
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
    access_subkeys=None,
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
                access_subkeys=access_subkeys,
            )
    assign_new_resource_to_service(
        xresource,
        res_root_stack,
        arn_parameter,
        parameters,
        access_subkeys=access_subkeys,
    )
