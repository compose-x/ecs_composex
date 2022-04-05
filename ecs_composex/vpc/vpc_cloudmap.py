#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Handles mapping x-vpc to cloudmap resource
"""

import re

from troposphere import Ref

from .vpc_params import VPC_ID


def x_vpc_to_x_cloudmap(
    x_vpc, x_resource, property_stack, properties_to_update, property_name, settings
):
    """
    Updates properties of given resource with the VPC settings accordingly

    :param Vpc x_vpc:
    :param x_resource: The resource to update the attribute / property for
    :param ecs_composex.common.stacks.ComposeXStack property_stack:
    :param list properties_to_update:
    :param str property_name:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    vpc_prop_re = re.compile(r"^x-vpc(?:::(?P<attribute>[a-zA-Z0-9]+))?$")
    for prop in properties_to_update:
        if not isinstance(prop, str):
            continue
        parts = vpc_prop_re.match(prop)
        if not parts:
            continue
        if parts.group("attribute"):
            for attr_parameter, attr_value in x_vpc.attributes_outputs.items():
                if attr_parameter.title == parts.group("attribute"):
                    setattr(x_resource, property_name, Ref(attr_parameter))
        else:
            setattr(x_resource, property_name, Ref(x_vpc.attributes_outputs[VPC_ID]))
