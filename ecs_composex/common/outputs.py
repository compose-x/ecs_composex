#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to format CFN template Outputs
"""

from troposphere import (
    AWS_STACK_NAME,
    AWSHelperFn,
    AWSObject,
    Export,
    If,
    ImportValue,
    Output,
    Sub,
)

from ecs_composex.common import LOG
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, Parameter
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER


def validate(value):
    """
    Method to validate the input
    :raises: ValueError
    """
    if not len(value) == 3:
        raise ValueError(
            "Output argument expects Name, AttributeName, Value. Only got", len(value)
        )
    if not isinstance(value[0], (Parameter, str)):
        raise TypeError("Name should be of type", str, Parameter, "Got", type(value[0]))
    if not isinstance(value[1], str):
        raise TypeError("AttributeName should be of type", str, "Got", type(value[1]))

    valid_type = issubclass(type(value[2]), AWSHelperFn)
    if not (valid_type or isinstance(value[2], (str, int))):
        raise TypeError("Value type is", type(value[2]), "Expected", str, AWSHelperFn)


class ComposeXOutput(object):
    """
    Class to make the output easier.
    """

    delim = CFN_EXPORT_DELIMITER
    stack_string_base = f"${{{AWS_STACK_NAME}}}{delim}"
    root_string_base = f"${{{ROOT_STACK_NAME_T}}}{delim}"

    def __init__(self, resource, values, export=True, duplicate_attr=False):
        """
        Initialize the output class.

        :param resource: The object to export attributes for.
        :param bool export:
        """
        self.object_repr = None
        self.duplicate_attr = duplicate_attr
        self.validate_input(resource, values, export, duplicate_attr)
        self.values = values
        self.outputs = []

        for value in self.values:
            if not isinstance(value, tuple):
                raise TypeError(
                    "All values should be a tuple of (str, value). Got", type(value)
                )
            validate(value)
            attr_name = (
                value[0] if not isinstance(value[0], Parameter) else value[0].title
            )
            output_ext = value[1]
            attr_value = value[2]
            stack_string = (
                f"{self.stack_string_base}{self.object_repr}{self.delim}{attr_name}"
            )
            root_string = (
                f"{self.root_string_base}{self.object_repr}{self.delim}{attr_name}"
            )
            output_name = f"{self.object_repr}{output_ext}"
            output = Output(output_name, Value=attr_value)
            if export:
                output.Export = Export(
                    If(USE_STACK_NAME_CON_T, Sub(stack_string), Sub(root_string))
                )
            self.outputs.append(output)
            if self.duplicate_attr:
                output = Output(attr_name, Value=attr_value)
                self.outputs.append(output)

    def validate_input(self, resource, values, export=True, duplicate_attr=False):
        if issubclass(type(resource), AWSObject) and hasattr(resource, "title"):
            self.object_repr = resource.title
        elif isinstance(resource, str):
            self.object_repr = resource
        elif isinstance(resource, Parameter):
            self.object_repr = resource.title
        elif resource is None:
            self.object_repr = ""
            if duplicate_attr:
                self.duplicate_attr = False
        else:
            raise TypeError(
                "object should be a subclass of", AWSObject, "Got", type(resource)
            )
        if not isinstance(values, list):
            raise TypeError("values must be of type", list)


def get_import_value(title, attribute_name, delimiter=None):
    """
    Wrapper function to define ImportValue for defined resource name

    :param title: name of the resource exported
    :param attribute_name: attribute exported
    :param delimiter: delimiter between stack name, resource name and attribute
    :return:
    """

    if delimiter is None:
        delimiter = CFN_EXPORT_DELIMITER
    elif not isinstance(delimiter, str):
        LOG.error(
            f"delimiter must be of type str, got {type(delimiter)}. Setting to default"
        )
        delimiter = CFN_EXPORT_DELIMITER
    return ImportValue(
        Sub(f"${{{ROOT_STACK_NAME_T}}}{delimiter}{title}{delimiter}{attribute_name}")
    )
