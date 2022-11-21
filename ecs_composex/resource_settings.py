# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle resource settings definition to containers.
"""
from __future__ import annotations

import copy
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.x_resources import XResource
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import keyisset
from troposphere import AWSHelperFn, GetAtt, NoValue, Ref, Sub
from troposphere.ecs import Environment
from troposphere.iam import Policy as IamPolicy
from troposphere.iam import PolicyType

from ecs_composex.common.cfn_params import STACK_ID_SHORT, Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import add_parameters, add_update_mapping
from ecs_composex.compose.compose_services.helpers import extend_container_envvars
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.kms.kms_params import MAPPINGS_KEY as KMS_MAPPING_KEY
from ecs_composex.kms.kms_params import MOD_KEY as KMS_MOD


def get_parameter_settings(resource, parameter: Parameter) -> tuple:
    """
    Function to define a set of values for the purpose of exposing resources settings from their stack to another.

    :param ecs_composex.compose.x_resources.XResource resource: The XResource we want to extract the outputs from
    :param parameter: The parameter we want to extract the outputs for
    :return: Ordered combination of settings
    :rtype: tuple
    """
    try:
        data = (
            resource.attributes_outputs[parameter]["Name"],
            resource.attributes_outputs[parameter]["ImportParameter"],
            resource.attributes_outputs[parameter]["ImportValue"],
            parameter,
        )
        return data
    except KeyError as error:
        print(error)
        print([r.title for r in resource.output_properties.keys()])
        print(resource.attributes_outputs.items())
        if isinstance(parameter, Parameter):
            print(parameter, parameter.title)
        print(f"{resource.module.res_key}.{resource.name}")
        raise


def determine_arns(arn, policy_doc, ignore_missing_primary=False) -> list:
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


def get_access_type_policy_model(
    access_type, policies_models, access_subkey: str = None
) -> dict:
    """

    :param str|dict access_type:
    :param dict policies_models:
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


def get_att_already_set(
    existing_arns: list, cfn_type, get_object, get_prop: str
) -> bool:
    """
    Compares a list of
    :param existing_arns:
    :param get_object:
    :param get_prop:
    :return:
    """
    for arn in existing_arns:
        if isinstance(arn, cfn_type):
            _object = arn.data["Fn::GetAtt"][0]
            _prop = arn.data["Fn::GetAtt"][1]
            LOG.debug("Already have a ", _object, _prop)
            if get_object == _object and get_prop == _prop:
                return True
    return False


def add_new_arns_to_statement_resource(existing_arns: list, new_arns: list):
    """
    Identifies if an ARN in the new arns to add already is set. Returns the list of
    non duplicate ARNs to add to statement

    if type of input is unmanaged, add to the list anyway...

    :param existing_arns:
    :param new_arns:
    """
    for new_arn in new_arns:
        if isinstance(new_arn, GetAtt):
            get_object = new_arn.data["Fn::GetAtt"][0]
            get_prop = new_arn.data["Fn::GetAtt"][1]
            if not get_att_already_set(existing_arns, (GetAtt,), get_object, get_prop):
                existing_arns.append(new_arn)
        elif isinstance(new_arn, str):
            if new_arn not in existing_arns:
                existing_arns.append(new_arn)
        else:
            existing_arns.append(new_arn)


def define_iam_permissions(
    resource_mapping_key,
    dest_resource,
    dest_resource_template,
    policy_title,
    access_type_policy_model,
    access_definition: Union[str, dict],
    resource_arns,
    access_subkey: str = None,
    roles=None,
    sid_override: str = None,
) -> None:
    """
    If a policy already exists to manage resources of the same AWS Service, imports the policy, else, creates one.
    The SID of the policy allows grouping resources that have a similar access pattern together in the same
    statement policy, reducing the policy length (later, might allow for managed policies).
    If there were no SID set already in a statement, adds it.

    :param resource_mapping_key:
    :param dest_resource:
    :param troposphere.Template dest_resource_template:
    :param str policy_title:
    :param dict access_type_policy_model:
    :param str, dict access_definition:
    :param list resource_arns:
    :param str access_subkey:
    :param list roles: List of Role pointers to use as Policy targets
    """
    new_policy_statement = copy.deepcopy(access_type_policy_model)
    sid_name = (
        set_sid_name(access_definition, access_subkey)
        if not sid_override
        else sid_override
    )
    if (
        resource_mapping_key
        not in dest_resource.iam_manager.iam_modules_policies.keys()
    ):
        dest_resource.iam_manager.iam_modules_policies[
            resource_mapping_key
        ] = PolicyType(
            policy_title,
            PolicyName=policy_title,
            PolicyDocument={"Version": "2012-10-17", "Statement": []},
            Roles=roles,
        )
        res_policy = dest_resource_template.add_resource(
            dest_resource.iam_manager.iam_modules_policies[resource_mapping_key]
        )
    else:
        res_policy = dest_resource.iam_manager.iam_modules_policies[
            resource_mapping_key
        ]
    policy_doc = getattr(res_policy, "PolicyDocument")
    policy_doc_statement = policy_doc["Statement"]
    for statement in policy_doc_statement:
        if keyisset("Sid", statement) and statement["Sid"] == sid_name:
            if not isinstance(statement["Resource"], list):
                statement["Resource"] = [statement["Resource"]]
            add_new_arns_to_statement_resource(statement["Resource"], resource_arns)
            break
    else:
        new_policy_statement["Sid"] = sid_name
        new_policy_statement["Resource"] = (
            resource_arns if isinstance(resource_arns, list) else [resource_arns]
        )
        policy_doc_statement.append(new_policy_statement)


def set_update_container_env_vars_from_resource_attribute(
    svc_container_environment: list,
    svc: ComposeService,
    resource: XResource,
    target: tuple,
) -> None:
    """
    For each environment variable set, if it is a string matching the regular expression,
    replace environment variable value with resource attribute ``ReturnValue``

    :param svc_container_environment:
    :param svc:
    :param resource:
    :param target:
    :return:
    """
    resource_attribute_match_re = re.compile(
        r"^(?P<res_key>x-[\S]+)::(?P<res_name>[\S]+)::(?P<return_value>[\S]+)$"
    )
    for defined_env_var in svc_container_environment:
        value = (
            defined_env_var.Value
            if isinstance(defined_env_var, Environment)
            else defined_env_var
        )
        if not isinstance(value, str):
            continue
        parts = resource_attribute_match_re.match(value)
        if not parts or not (
            parts.group("res_name") == resource.name
            and parts.group("res_key") == resource.module.res_key
        ):
            continue
        extend_container_envvars(
            svc.container_definition,
            resource.set_update_container_env_var(
                target, parts.group("return_value"), defined_env_var.Name
            ),
            replace=True,
        )


def map_resource_env_vars_to_family_service_environment(
    target: tuple, resource: XResource
) -> None:
    """
    Function to expose environment variables to a specific container service from a given x-resource
    based on the environment defined in the service definition.

    These take precedence ReturnValues settings which would be applied to all containers in the family

    :param tuple target:
    :param XResource resource:
    """

    for svc in target[2]:
        if svc in target[0].managed_sidecars:
            continue
        if not hasattr(svc.container_definition, "Environment"):
            continue
        svc_container_environment = svc.container_definition.Environment
        if svc_container_environment == NoValue:
            continue
        set_update_container_env_vars_from_resource_attribute(
            svc_container_environment, svc, resource, target
        )


def map_resource_env_vars_to_family_services(
    target,
    resource,
) -> None:
    """
    Function to deal with the env vars to add to the family stack based on the resource
    Services definition

    :param tuple target:
    :param ecs_composex.compose.x_resources.XResource resource:
    """
    map_resource_env_vars_to_family_service_environment(target, resource)
    return_values = (
        {} if not keyisset("ReturnValues", target[-1]) else target[-1]["ReturnValues"]
    )
    if return_values:
        env_vars = resource.generate_resource_service_env_vars(target, return_values)
    else:
        env_vars = resource.generate_ref_env_var(target)
    for svc in target[2]:
        extend_container_envvars(
            svc.container_definition,
            env_vars,
        )


def map_resource_return_value_to_services_command(
    family: ComposeFamily, settings: ComposeXSettings
) -> None:
    """
    Checks if their is a x-<res_key>::<name>::<return_value>
    """
    resource_attribute_match_re = re.compile(
        r"^(?P<res_key>x-[\S]+)::(?P<res_name>[\S]+)::(?P<return_value>[\S]+)$"
    )
    from itertools import chain

    for service in chain(family.managed_sidecars, family.ordered_services):
        if not hasattr(service.container_definition, "Command"):
            continue
        command = getattr(service.container_definition, "Command")
        if command == NoValue:
            continue
        new_command = []
        for sh_part in command:
            parts = resource_attribute_match_re.match(sh_part)
            if not parts:
                new_command.append(sh_part)
                continue
            resource = settings.find_resource(
                f"{parts.group('res_key')}::{parts.group('res_name')}"
            )
            if (
                parts.group("return_value")
                not in resource.property_to_parameter_mapping
            ):
                raise KeyError(
                    parts.group("return_value"),
                    "not a valid return value for",
                    resource.module.res_key,
                    resource.name,
                    resource.property_to_parameter_mapping.keys(),
                )
            parameter = resource.property_to_parameter_mapping[
                parts.group("return_value")
            ]
            res_param_id = resource.add_parameter_to_family_stack(
                family, settings, parameter
            )
            if res_param_id is resource:
                new_command.append(Ref(resource.cfn_resource))
            elif res_param_id is not resource and resource.cfn_resource:
                new_command.append(Ref(res_param_id["ImportParameter"]))
            else:
                new_command.append(res_param_id["ImportValue"])
        service.command = new_command


def map_service_perms_to_resource(
    family: ComposeFamily,
    target,
    arn_value,
    resource=None,
    resource_policies=None,
    resource_mapping_key=None,
    access_definition=None,
    access_subkey=None,
    ignore_missing_primary=False,
) -> None:
    """
    Maps the resource to the services / target family. Sets up IAM and environment variables

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param tuple target:
    :param arn_value:
    :param ecs_composex.compose.x_resources.XResource resource:
    :param dict resource_policies:
    :param str resource_mapping_key:
    :param str,dict access_definition:
    :param str access_subkey:
    :param bool ignore_missing_primary:
    """

    if not resource and not resource_policies and not resource_mapping_key:
        raise ValueError(
            "You must specify either resource or resource_policies and resources_mappings"
        )
    resource_policies = resource.policies_scaffolds if resource else resource_policies
    resource_mapping_key = (
        resource.module.mapping_key if resource else resource_mapping_key
    )
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
        family.template,
        policy_title,
        access_type_policy_model,
        access_definition,
        resource_arns,
        access_subkey=access_subkey,
        roles=[family.iam_manager.task_role.name],
    )


def map_x_resource_perms_to_resource(
    dest_resource: XResource,
    arn_value,
    access_definition,
    resource=None,
    resource_policies=None,
    resource_mapping_key=None,
    access_subkey=None,
    ignore_missing_primary=False,
) -> None:
    """
    Maps an x-resource to another's IAM Manager

    :param XResource dest_resource:
    :param arn_value:
    :param ecs_composex.compose.x_resources.XResource resource:
    :param dict resource_policies:
    :param str resource_mapping_key:
    :param str,dict access_definition:
    :param str access_subkey:
    :param bool ignore_missing_primary:
    """
    if not dest_resource.iam_manager:
        return

    if not resource and not resource_policies and not resource_mapping_key:
        raise ValueError(
            "You must specify either resource or resource_policies and resources_mappings"
        )
    resource_policies = resource.policies_scaffolds if resource else resource_policies
    resource_mapping_key = (
        resource.module.mapping_key if resource else resource_mapping_key
    )
    policies_models = (
        deepcopy(resource_policies)
        if not access_subkey
        else deepcopy(resource_policies[access_subkey])
    )
    access_type_policy_model = get_access_type_policy_model(
        access_definition, policies_models, access_subkey
    )
    resource_arns = determine_arns(
        arn_value, access_type_policy_model, ignore_missing_primary
    )
    policy_title = f"{dest_resource.logical_name}To{resource_mapping_key}"
    define_iam_permissions(
        resource_mapping_key,
        dest_resource,
        dest_resource.stack.stack_template,
        policy_title,
        access_type_policy_model,
        access_definition,
        resource_arns,
        access_subkey=access_subkey,
        roles=[Ref(dest_resource.iam_manager.service_linked_role)],
    )


def handle_kms_access(settings: ComposeXSettings, resource, target):
    """
    Function to map KMS permissions for the services which need access to a resource using a KMS Key

    :param ecs_composex.common.settings.ComposeXSettings settings: Here for future work
    :param ecs_composex.common.compose_resources.XResource resource: The lookup resource
    :param tuple target:
    """
    key_arn = resource.attributes_outputs[resource.kms_arn_attr]["ImportValue"]
    map_service_perms_to_resource(
        target[0],
        target,
        access_definition="EncryptDecrypt",
        arn_value=key_arn,
        resource_policies=get_access_types(KMS_MOD),
        resource_mapping_key=KMS_MAPPING_KEY,
    )


def set_arn_att_value(resource, arn_settings, arn_parameter) -> AWSHelperFn:
    """

    :param ecs_composex.common.compose_resources.ServicesXResource resource: The resource
    :param tuple arn_settings:
    :param ecs_composex.common.cfn_params.Parameter arn_parameter:
    :return:
    """
    if resource.cfn_resource:
        arn_attr_value = Ref(arn_settings[1])
    elif resource.mappings:
        arn_attr_value = resource.attributes_outputs[arn_parameter]["ImportValue"]
    else:
        raise AttributeError(
            f"{resource.module.res_key}.{resource.name} - Unable to define ARN Attribute"
        )
    return arn_attr_value


def import_resource_into_service_stack(
    settings: ComposeXSettings,
    resource,
    family: ComposeFamily,
    params_to_add,
    params_values,
) -> None:
    """
    Function to either add parameters to the services stack or mapping for a given resource

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.compose_resources.ServicesXResource resource: The resource
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param list[ecs_composex.common.cfn_params.Parameter] params_to_add:
    :param dict params_values:
    """
    if resource.cfn_resource:
        add_parameters(family.template, params_to_add)
        family.stack.Parameters.update(params_values)
    elif resource.mappings:
        add_update_mapping(
            family.template,
            resource.module.mapping_key,
            settings.mappings[resource.module.mapping_key],
        )


def add_dependency(resource, family: ComposeFamily, settings: ComposeXSettings) -> None:
    """
    Add dependency across the resource stack and the ECS Service stack

    :param ecs_composex.common.compose_resources.ServicesXResource resource: The resource
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param settings:
    """
    resource_top_stack = resource.stack.get_top_root_stack(settings.root_stack)
    if (
        resource.stack
        and not resource.stack.is_void
        and resource_top_stack.title not in family.stack.DependsOn
    ):
        family.stack.DependsOn.append(resource_top_stack.title)


def link_resource_kms_to_service(settings: ComposeXSettings, resource, target) -> None:
    """
    Links the KMS key of a given resource (if necessary) to the service in order to use that key
    Avoids having to do x-kms.Lookup to a service

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.compose_resources.ServicesXResource resource: The resource
    :param tuple target:
    :return:
    """
    if (
        hasattr(resource, "kms_arn_attr")
        and resource.kms_arn_attr
        and keyisset(resource.kms_arn_attr, resource.lookup_properties)
    ):
        handle_kms_access(settings, resource, target)


def set_iam_link_resource_to_services(
    resource, target, arn_attr_value: AWSHelperFn, access_subkeys: list = None
) -> None:
    """
    Sets IAM Permissions to the ECS Service to access the resource

    :param resource:
    :param target:
    :param arn_attr_value:
    :param access_subkeys:
    :return:
    """
    if access_subkeys:
        for access_subkey in access_subkeys:
            if access_subkey not in target[3]:
                continue
            map_service_perms_to_resource(
                target[0],
                target,
                arn_value=arn_attr_value,
                resource=resource,
                access_subkey=access_subkey,
            )
    else:
        map_service_perms_to_resource(
            target[0], target, resource=resource, arn_value=arn_attr_value
        )


def link_resource_to_services(
    settings: ComposeXSettings,
    resource,
    arn_parameter: Parameter,
    access_subkeys: list = None,
    targets_overrides: list = None,
) -> None:
    """
    Function to assign the new resource to the service/family using it.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.compose_resources.ServicesXResource resource: The resource
    :param ecs_composex.common.cfn_parameter.Parameter arn_parameter: The parameter mapping to the ARN attribute
    :param list[str] access_subkeys: Allows to access subkeys from the resource policies
    """
    arn_settings = get_parameter_settings(resource, arn_parameter)
    params_to_add = [arn_settings[1]]
    params_values = {arn_settings[0]: arn_settings[2]}

    arn_attr_value = set_arn_att_value(resource, arn_settings, arn_parameter)

    targets = resource.families_targets if not targets_overrides else targets_overrides
    for target in targets:
        if target[0] and (not target[0].stack or not target[0].template):
            continue
        import_resource_into_service_stack(
            settings, resource, target[0], params_to_add, params_values
        )
        map_resource_env_vars_to_family_services(target, resource)
        if not target[3]:
            LOG.warning(
                f"{resource.module.res_key}.{resource.name} - Access not defined for {target[0].name}"
            )
            continue
        set_iam_link_resource_to_services(
            resource, target, arn_attr_value, access_subkeys
        )
        if resource.cfn_resource:
            add_dependency(resource, target[0], settings)
        link_resource_kms_to_service(settings, resource, target)


def handle_resource_to_services(
    settings: ComposeXSettings,
    x_resource,
    arn_parameter,
    nested=False,
    access_subkeys=None,
    targets_overrides: list = None,
):
    """
    Function to evaluate the type of resource coming in and pass on the settings and parameters for
    IAM and otherwise assignment

    :param ecs_composex.common.compose_resource.XResource x_resource:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param arn_parameter:
    :param bool nested:
    :param list targets_overrides: overrides the list of targets to process for the resource
    """
    if x_resource.stack and not x_resource.stack.is_void:
        for (
            resource_name,
            s_resource,
        ) in x_resource.stack.stack_template.resources.items():
            if issubclass(type(s_resource), ComposeXStack):
                handle_resource_to_services(
                    settings,
                    s_resource,
                    arn_parameter,
                    nested=True if nested is False else nested,
                    access_subkeys=access_subkeys,
                    targets_overrides=targets_overrides,
                )
    link_resource_to_services(
        settings=settings,
        resource=x_resource,
        arn_parameter=arn_parameter,
        access_subkeys=access_subkeys,
        targets_overrides=targets_overrides,
    )
