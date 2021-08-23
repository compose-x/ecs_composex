#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for the XStack SSM
"""
import json
from os import path

import yaml
from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, Ref, Sub
from troposphere.ssm import Parameter as CfnSsmParameter
from yaml import Loader

from ecs_composex.common import LOG, add_outputs, build_template
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resources_import import import_record_properties
from ecs_composex.ssm_parameter.ssm_parameter_ecs import create_ssm_param_mappings
from ecs_composex.ssm_parameter.ssm_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    SSM_PARAM_ARN,
    SSM_PARAM_NAME,
)
from ecs_composex.ssm_parameter.ssm_perms import get_access_types


def handle_yaml_validation(resource, value, file_path):
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


def handle_json_validation(resource, value, file_path):
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


def import_value_from_file(resource):
    """
    Function to import file into the SSM Parameter value
    :param SsmParameter resource:
    :return: The value
    :rtype: str
    """
    file_path = path.abspath(resource.parameters["FromFile"])
    with open(file_path, "r") as file_fd:
        value = file_fd.read()
    if keyisset("ValidateJson", resource.parameters):
        return handle_json_validation(resource, value, file_path)
    elif keyisset("ValidateYaml", resource.parameters):
        return handle_yaml_validation(resource, value, file_path)
    return value


def render_new_parameters(new_resources, root_stack):
    """

    :param list[SsmParameter] new_resources:
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :return:
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
        new_res.properties.update({"Value": value})
        param_props = import_record_properties(
            new_res.properties, CfnSsmParameter, ignore_missing_required=False
        )
        new_res.cfn_resource = CfnSsmParameter(new_res.logical_name, **param_props)
        root_stack.stack_template.add_resource(new_res.cfn_resource)
        new_res.init_outputs()
        new_res.generate_outputs()
        add_outputs(root_stack.stack_template, new_res.outputs)


class SsmParameter(XResource):
    """
    Class to represent a SQS Queue
    """

    policies_scaffolds = get_access_types()

    def init_outputs(self):
        self.output_properties = {
            SSM_PARAM_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            SSM_PARAM_ARN: (
                self.logical_name,
                self.cfn_resource,
                Sub,
                f"arn:{{{AWS_PARTITION}}}:ssm:{{{AWS_REGION}}}:{{{AWS_ACCOUNT_ID}}}:parameter:"
                f"{self.logical_name.title()}",
            ),
        }


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(
            settings, SsmParameter, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY
        )
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            template = build_template("Parent template for SSM in ECS Compose-X")
            super().__init__(title, stack_template=template, **kwargs)
            render_new_parameters(new_resources, self)
        else:
            self.is_void = True
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            create_ssm_param_mappings(
                settings.mappings[RES_KEY], lookup_resources, settings
            )
