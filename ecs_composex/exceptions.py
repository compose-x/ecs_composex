#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Custom exceptions for compose-x
"""

from .cloudmap.cloudmap_stack import PrivateNamespace


class ComposeXceptions(Exception):
    """
    Top class for Compose-X Exceptions
    """

    pass


class IncompatibleOptions(ComposeXceptions):
    """
    Exception when two x-resources conflict, i.e. when you try to use Lookup on x-cloudmap and create a new VPC
    """

    pass


class ConflictingSettings(ComposeXceptions):
    """
    Exception for conflicting settings for a service family or x-resource properties
    """


def x_cloud_lookup_and_new_vpc(settings, vpc_stack):
    """
    Function to ensure there is no x-cloudmap.Lookup resource and Compose-X is creating a new VPC.
    The Namespace (CloudMap PrivateNamespace) cannot span across multiple VPC

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param vpc_stack: The VPC Stack
    :raises: IncompatibleOptions
    """
    lookup_namespaces = [
        namespace
        for namespace in settings.x_resources
        if isinstance(namespace, PrivateNamespace) and namespace.lookup_properties
    ]
    if lookup_namespaces and not vpc_stack.is_void:
        raise IncompatibleOptions(
            "You cannot have Compose-X Create a new VPC and use x-cloudmap.Lookup."
            " Use x-vpc to re-use the VPC the PrivateNamespace is attached to",
            lookup_namespaces,
        )
