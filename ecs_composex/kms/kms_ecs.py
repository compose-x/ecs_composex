#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to manage IAM policies to grant access to ECS Services to KMS Keys
"""

from troposphere.kms import Key

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kms.kms_params import KMS_KEY_ARN_T
from ecs_composex.kms.kms_perms import ACCESS_TYPES
from ecs_composex.resource_permissions import apply_iam_based_resources
from ecs_composex.resource_settings import (
    generate_resource_permissions,
)


def handle_new_keys(
    xresources,
    services_families,
    services_stack,
    res_root_stack,
    l_keys,
    nested=False,
):
    keys_r = []
    s_resources = res_root_stack.stack_template.resources
    for resource_name in s_resources:
        if isinstance(s_resources[resource_name], Key):
            keys_r.append(s_resources[resource_name].title)
        elif issubclass(type(s_resources[resource_name]), ComposeXStack):
            handle_new_keys(
                xresources,
                services_families,
                services_stack,
                s_resources[resource_name],
                l_keys,
                nested=True,
            )

    for key_name in xresources:
        key = xresources[key_name]
        if key.logical_name in keys_r:
            perms = generate_resource_permissions(
                key.logical_name, ACCESS_TYPES, KMS_KEY_ARN_T
            )
            apply_iam_based_resources(
                key,
                services_families,
                services_stack,
                res_root_stack,
                perms,
                nested,
            )
            del l_keys[key_name]


def kms_to_ecs(xresources, services_stack, services_families, res_root_stack, settings):
    """
    Function to link the resource and the ECS Services.

    :param dict xresources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param dict services_families:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    l_keys = xresources.copy()
    handle_new_keys(
        xresources, services_families, services_stack, res_root_stack, l_keys
    )
