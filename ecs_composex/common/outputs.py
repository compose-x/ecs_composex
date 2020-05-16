# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

"""
Functions to format CFN template Outputs
"""

from troposphere import Output, Export, Sub, If, ImportValue
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T


def cfn_resource_type(object_name, strip=True):
    """Returns the Resource Type property removing the AWS:: prefix

    :returns: res_type
    :rtype: str
    """
    res_type = object_name.resource_type.replace(":", "")
    if strip:
        return res_type.replace("AWS", "")
    return res_type


def formatted_outputs(comments, obj_name=None, export=True, delimiter=None):
    """Function to format the outputs easily and add exports based on a prefix

    :param delimiter: delimimiter to use between parts of the export
    :param comments: List of KeyPair values representing the output
    :type comments: list
    :param export: Whether or not this output should export to CFN Exports. Default: False
    :type export: bool
    :param prefix: prefix for the cfn exports. Must enable uniqueness of the output in CFN
    :type prefix: str
    :param use_root_stack: Whether this output for prefix should use the RootStackName as prefix
    :type use_root_stack: bool

    :return: outputs
    :rtype: list
    """
    outputs = []
    if delimiter is None:
        delimiter = CFN_EXPORT_DELIMITER
    if isinstance(obj_name, str):
        obj_name = f"{delimiter}{obj_name}"
    elif obj_name is not None and hasattr(obj_name, "title"):
        obj_name = f"{delimiter}${{{obj_name.title}}}"
    elif obj_name is None:
        obj_name = ""
    if isinstance(comments, list):
        for comment in comments:
            if isinstance(comment, dict):
                keys = list(comment.keys())
                title = keys[0]
                args = {"title": title, "Value": comment[title]}
                if export:
                    args["Export"] = Export(
                        If(
                            USE_STACK_NAME_CON_T,
                            Sub(f"${{AWS::StackName}}{obj_name}{delimiter}{title}"),
                            Sub(
                                f"${{{ROOT_STACK_NAME_T}}}{obj_name}{delimiter}{title}"
                            ),
                        )
                    )
                output = Output(**args)
                outputs.append(output)
    return outputs


def define_import(resource_name, attribute_name, delimiter=None):
    """
    Wrapper function to define ImportValue for defined resource name

    :param delimiter: delimiter between stack name, resource name and attribute
    :param resource_name: name of the resource exported
    :param attribute_name: attribute exported
    :type attribute_name: str
    :type resource_name: str
    :return:
    """

    if delimiter is None:
        delimiter = CFN_EXPORT_DELIMITER
    return If(
        USE_STACK_NAME_CON_T,
        ImportValue(
            Sub(
                f"${{AWS::StackName}}{delimiter}{resource_name}{delimiter}{attribute_name}"
            )
        ),
        ImportValue(
            Sub(
                f"${{{ROOT_STACK_NAME_T}}}{delimiter}{resource_name}{delimiter}{attribute_name}"
            )
        ),
    )
