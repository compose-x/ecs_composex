#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""Common Conditions across the templates"""

from troposphere import Condition, Equals, If, Not, Ref

from ecs_composex.common import cfn_params

USE_STACK_NAME_CON_T = "UseStackName"
USE_STACK_NAME_CON = Equals(
    Ref(cfn_params.ROOT_STACK_NAME), cfn_params.ROOT_STACK_NAME.Default
)


USE_SPOT_CON_T = "UseSpotFleetHostsCondition"
USE_SPOT_CON = Equals(Ref(cfn_params.USE_FLEET), "True")

NOT_USE_SPOT_CON_T = "NotUseSpotFleetHostsCondition"
NOT_USE_SPOT_CON = Not(Condition(USE_SPOT_CON_T))


def pass_root_stack_name():
    """
    Function to add root_stack to a stack parameters

    :return: rootstack name value based on condition
    """
    return {
        cfn_params.ROOT_STACK_NAME_T: If(
            USE_STACK_NAME_CON_T, Ref("AWS::StackName"), Ref(cfn_params.ROOT_STACK_NAME)
        )
    }


def define_stack_name(template=None):
    """
    Function to return Stack name contstruct.
    Adds the conditions and parameters if template is given.

    :param troposphere.Template template: the template to add it to.
    :return:
    """
    if template and USE_STACK_NAME_CON_T not in template.conditions:
        template.add_condition(USE_STACK_NAME_CON_T, USE_STACK_NAME_CON)
    return If(
        USE_STACK_NAME_CON_T, Ref("AWS::StackName"), Ref(cfn_params.ROOT_STACK_NAME)
    )
