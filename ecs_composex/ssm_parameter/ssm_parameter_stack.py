#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for the XStack SSM
"""
import logging
from os import path

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref
from troposphere.ssm import Parameter as CfnSsmParameter

from ecs_composex.common import LOG, build_template
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.resources_import import import_record_properties
from ecs_composex.ssm_parameter.ssm_params import (
    MOD_KEY,
    RES_KEY,
    SSM_PARAM_NAME,
    SSM_PARAM_TYPE,
)
from ecs_composex.ssm_parameter.ssm_perms import get_access_types


def render_new_parameters(new_resources, root_stack):
    """

    :param list[SsmParameter] new_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
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
            with open(path.abspath(new_res.parameters["FromFile"]), "r") as file_fd:
                value = file_fd.read()
        if keyisset("Value", new_res.properties) and value:
            LOG.warn(
                "Both Value and FromFile properties were set. Using Value from Properties"
            )
            value = new_res.properties["Value"]
        elif not keyisset("Value", new_res.properties) and value:
            new_res.properties.update({"Value": value})
        param_props = import_record_properties(
            new_res.properties, CfnSsmParameter, ignore_missing_required=False
        )
        new_res.cfn_resource = CfnSsmParameter(new_res.logical_name, **param_props)
        root_stack.stack_template.add_resource(new_res.cfn_resource)


class SsmParameter(XResource):
    """
    Class to represent a SQS Queue
    """

    policies_scaffolds = get_access_types()

    def init_outputs(self):
        self.output_properties = {
            SSM_PARAM_NAME: (self.logical_name, self.cfn_resource, Ref, None, "Url"),
            SSM_PARAM_TYPE: (
                f"{self.logical_name}{SSM_PARAM_TYPE.return_value}",
                self.cfn_resource,
                GetAtt,
                SSM_PARAM_TYPE.return_value,
                "Arn",
            ),
        }


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, SsmParameter, RES_KEY, MOD_KEY)
        new_queues = [
            queue
            for queue in settings.compose_content[RES_KEY].values()
            if not queue.lookup and not queue.use
        ]
        if new_queues:
            template = build_template("Parent template for SQS in ECS Compose-X")
            super().__init__(title, stack_template=template, **kwargs)
            render_new_parameters(new_queues, self)
        else:
            self.is_void = True

        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
