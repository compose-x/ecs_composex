#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import warnings
from re import sub

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.ecs_composex import X_KEY


def set_new_resources(x_resources, res_key, supports_uses_default=False):
    """
    Function to create a list of new resources. Check if empty resource is supported

    :param list[XResource] x_resources:
    :param str res_key:
    :param bool supports_uses_default:
    :return: list of resources to create
    :rtype: list[XResource] x_resources:
    """
    new_resources = []
    for resource in x_resources:
        if (
            resource.properties or resource.parameters or resource.uses_default
        ) and not (resource.lookup or resource.use):
            if resource.uses_default and not supports_uses_default:
                raise KeyError(
                    f"{res_key}.{resource.name} - Requires either or both Properties or MacroParameters. Got neither",
                    resource.definition.keys(),
                )
            new_resources.append(resource)
    return new_resources


def set_lookup_resources(x_resources, res_key):
    """

    :param list[XResource] x_resources:
    :param str res_key:
    :return: list of resources to import from Lookup
    :rtype: list[XResource] x_resources:
    """
    lookup_resources = []
    for resource in x_resources:
        if resource.lookup:
            if resource.properties or resource.parameters or resource.use:
                LOG.warning(
                    f"{resource.module_name}.{resource.name} is set for Lookup"
                    " but has other properties set. Voiding them"
                )
                resource.properties = {}
                resource.parameters = {}
                resource.use = {}
            lookup_resources.append(resource)
    return lookup_resources


def set_use_resources(x_resources, res_key, use_supported=False):
    """

    :param list[XResource] x_resources:
    :param str res_key:
    :param bool use_supported:
    :return: list of resources to import from Use
    :rtype: list[XResource] x_resources:
    """
    use_resources = [
        resource
        for resource in x_resources
        if resource.use
        and not (resource.properties or resource.parameters or resource.lookup)
    ]
    if not use_supported and use_resources:
        warnings.warn(f"{res_key}.Use is not (yet) supported")
    return use_resources


def set_resources(settings, resource_class, res_key, mod_key=None, mapping_key=None):
    """
    Method to define the ComposeXResource for each service.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.compose_resources.XResource.__init__ resource_class:
    :param str res_key: The compose key identifier for resource
    :param str mod_key: The module name in ecs_composex mapping the resource type
    :param str mapping_key: The value of the Mapping map name for FindInMap
    """
    if not mod_key:
        mod_key = sub(X_KEY, "", res_key)
    if not keyisset(res_key, settings.compose_content):
        return
    for resource_name in settings.compose_content[res_key]:
        new_definition = resource_class(
            name=resource_name,
            definition=settings.compose_content[res_key][resource_name],
            module_name=mod_key,
            settings=settings,
            mapping_key=mapping_key,
        )
        LOG.debug(type(new_definition))
        LOG.debug(new_definition.__dict__)
        settings.compose_content[res_key][resource_name] = new_definition


def get_setting_key(name: str, settings_dict: dict) -> str:
    """
    Allows for flexibility in the syntax, i.e. to make access/Access both valid
    """
    if keyisset(name.title(), settings_dict):
        return name.title()
    return name
