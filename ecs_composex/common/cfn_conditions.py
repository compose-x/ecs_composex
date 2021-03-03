# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@compose-x.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Common Conditions across the templates"""

from troposphere import Condition, Not, Ref, Equals, If

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
