# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Most commonly used functions shared across all modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings import ComposeXSettings
    from .stacks import ComposeXStack

import re
from datetime import datetime as dt
from math import ceil, log
from uuid import uuid4

DATE = dt.utcnow().isoformat()
FILE_PREFIX = f'{dt.utcnow().strftime("%Y/%m/%d/%H%M")}/{str(uuid4().hex)[:6]}'
NONALPHANUM = re.compile(r"([^a-zA-Z\d]+)")


def clpow2(x):
    """
    Function to return the closest power of two from given x

    :param x: Number to look the closest power of two for

    :returns: int() closest power of two
    """
    return pow(2, int(log(x, 2) + 0.5))


def nxtpow2(x):
    """Function to find the next power of two from given x number

    :param x: number to look for the next power of two

    :returns: next power of two number
    """
    return int(pow(2, ceil(log(x, 2))))


def get_nested_property(top_object, property_path: str, separator: str = None):
    if separator is None:
        separator = r"."
    elif separator and not isinstance(separator, str):
        raise TypeError("Separator must be a string")
    top_property_split = property_path.split(separator, 1)
    if len(top_property_split) == 1 and hasattr(top_object, top_property_split[0]):
        return (
            top_object,
            top_property_split[0],
            getattr(top_object, top_property_split[0]),
        )
    if len(top_property_split) > 1 and hasattr(top_object, top_property_split[0]):
        return get_nested_property(
            getattr(top_object, top_property_split[0]), top_property_split[-1]
        )
    return None, None, None


# def add_parameter_recursively(
#     ext_stack: ComposeXStack,
#     compose_settings: ComposeXSettings,
#     attribute_settings: dict,
# ):
#     from .stacks import ComposeXStack
#
#     print(
#         "EXT STACK",
#         ext_stack,
#         type(ext_stack),
#         ext_stack.title
#         if isinstance(ext_stack, ComposeXStack)
#         else "NOT A COMPOSE STACK",
#     )
#     attribute_param = attribute_settings["ImportParameter"]
#
#     if (
#         ext_stack.parent_stack
#         and (ext_stack.parent_stack == compose_settings.root_stack)
#         or not ext_stack.parent_stack
#     ):
#         print("EXT STACK", ext_stack.title, "NO PARENT SET. UPDATING STACK PARAMETERS")
#         add_parameters(ext_stack.stack_template, [attribute_param])
#         ext_stack.Parameters.update(
#             {attribute_param.title: attribute_settings["ImportValue"]}
#         )
#     else:
#         add_parameters(ext_stack.stack_template, [attribute_param])
#         ext_stack.Parameters.update({attribute_param.title: Ref(attribute_param)})
#         return add_parameter_recursively(
#             ext_stack.parent_stack, compose_settings, attribute_settings
#         )
#     return Ref(attribute_param)
