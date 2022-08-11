#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ssm_parameter.ssm_parameter_stack import SsmParameter

import json
from os import path

import yaml
from compose_x_common.compose_x_common import keyisset
from troposphere import Base64
from troposphere.ssm import Parameter as CfnSsmParameter
from yaml import Loader

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_outputs
from ecs_composex.resources_import import import_record_properties
from ecs_composex.ssm_parameter.ssm_parameter_params import (
    SSM_PARAM_ARN,
    SSM_PARAM_NAME,
)


def get_parameter_config(parameter: SsmParameter, account_id: str, resource_id: str):
    """

    :param parameter:
    :param account_id:
    :param resource_id:
    :return:
    """
    return {SSM_PARAM_NAME.title: resource_id, SSM_PARAM_ARN.title: parameter.arn}


def handle_yaml_validation(resource: SsmParameter, value: str, file_path: str) -> str:
    """
    Function to evaluate the JSON content

    :param SsmParamter resource:
    :param str value: Value read from file
    :param str file_path:
    :return:
    """
    try:
        payload = yaml.load(value, Loader=Loader)
        if keyisset("RenderToJson", resource.parameters):
            return json.dumps(payload, separators=(",", ":"))
        return value
    except yaml.YAMLError:
        if keyisset("IgnoreInvalidYaml", resource.parameters):
            LOG.warn(
                f"{resource.name} - The content of {file_path} "
                "did not pass YAML validation. Skipping due to IgnoreInvalidYaml"
            )
            return value
        else:
            LOG.error(
                f"{resource.name} - The content of {file_path} "
                "did not pass YAML validation."
            )
            raise


def handle_json_validation(resource: SsmParameter, value: str, file_path: str) -> str:
    """
    Function to evaluate the JSON content

    :param SsmParamter resource:
    :param str value: Value read from file
    :param str file_path:
    :return:
    """
    try:
        payload = json.loads(value)
        if keyisset("MinimizeJson", resource.parameters):
            return json.dumps(payload, separators=(",", ":"))
        return value
    except json.decoder.JSONDecodeError:
        if keyisset("IgnoreInvalidJson", resource.parameters):
            LOG.warn(
                f"{resource.name} - The content of {file_path} "
                "did not pass JSON validation. Skipping due to IgnoreInvalidJson"
            )
            return value
        else:
            LOG.error(
                f"{resource.name} - The content of {file_path} "
                "did not pass JSON validation."
            )
            raise


def import_value_from_file(resource: SsmParameter) -> str | Base64:
    """
    Function to import file into the SSM Parameter value
    :param SsmParameter resource:
    :return: The value
    """
    file_path = path.abspath(resource.parameters["FromFile"])
    with open(file_path) as file_fd:
        value = file_fd.read()
    if keyisset("ValidateJson", resource.parameters):
        return handle_json_validation(resource, value, file_path)
    elif keyisset("ValidateYaml", resource.parameters):
        return handle_yaml_validation(resource, value, file_path)
    return value


def render_new_parameters(
    new_resources: list[SsmParameter], root_stack: ComposeXStack
) -> None:
    """

    :param list[SsmParameter] new_resources:
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    """
    for new_res in new_resources:
        value = None
        if (
            keyisset("Type", new_res.definition)
            and new_res.definition["Type"] == "SecureString"
        ):
            raise ValueError(f"{new_res.name} AWS CFN does not support SecureString.")
        if new_res.parameters and keyisset("FromFile", new_res.parameters):
            value = import_value_from_file(new_res)
        if keyisset("Value", new_res.properties):
            if value:
                LOG.warn(
                    "Both Value and FromFile properties were set. Using Value from Properties"
                )
            value = new_res.properties["Value"]
        if not value:
            raise ValueError(f"{new_res.name} - Failed to determine the value")
        if keyisset("EncodeToBase64", new_res.parameters):
            value = Base64(value)
        new_res.properties.update({"Value": value})
        param_props = import_record_properties(
            new_res.properties, CfnSsmParameter, ignore_missing_required=False
        )
        new_res.cfn_resource = CfnSsmParameter(new_res.logical_name, **param_props)
        root_stack.stack_template.add_resource(new_res.cfn_resource)
        new_res.init_outputs()
        new_res.generate_outputs()
        add_outputs(root_stack.stack_template, new_res.outputs)
