#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.compose.x_resources import XResource
    from ecs_composex.compose.x_resources.services_resources import ServicesXResource
    from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
    from ecs_composex.compose.x_resources.environment_x_resources import (
        AwsEnvironmentResource,
    )
    from ecs_composex.compose.x_resources.network_x_resources import (
        NetworkXResource,
        DatabaseXResource,
    )

from collections import OrderedDict

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG


def set_new_resources(
    x_resources: list[
        (
            XResource
            | ServicesXResource
            | ApiXResource
            | AwsEnvironmentResource
            | NetworkXResource
            | DatabaseXResource
        )
    ],
    supports_uses_default: bool = False,
):
    """
    Function to create a list of new resources. Check if empty resource is supported

    :param list[XResource] x_resources:
    :param bool supports_uses_default:
    :return: list of resources to create
    :rtype: list[XResource] x_resources:
    """
    new_resources = []
    for resource in x_resources:
        if (
            resource.properties or resource.parameters or resource.uses_default
        ) and not resource.lookup:
            if resource.uses_default and not supports_uses_default:
                raise KeyError(
                    f"{resource.module.res_key}.{resource.name} - "
                    "Requires either or both Properties or MacroParameters. Got neither",
                    resource.definition.keys(),
                )
            new_resources.append(resource)
    return new_resources


def set_lookup_resources(
    x_resources: list[
        (
            XResource
            | ServicesXResource
            | ApiXResource
            | AwsEnvironmentResource
            | NetworkXResource
            | DatabaseXResource
        )
    ],
):
    """

    :param list[XResource] x_resources:
    :return: list of resources to import from Lookup
    :rtype: list[XResource] x_resources:
    """
    lookup_resources = []
    for resource in x_resources:
        if resource.lookup:
            if resource.properties or resource.parameters:
                LOG.warning(
                    f"{resource.module.res_key}.{resource.name} is set for Lookup"
                    " but has other properties set. Voiding them"
                )
                resource.properties = {}
                resource.parameters = {}
            lookup_resources.append(resource)
    return lookup_resources


def set_resources(settings: ComposeXSettings, resource_class, module: XResourceModule):
    """
    Method to define the ComposeXResource for each service.
    First updates the resources dict

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.compose_resources.XResource resource_class:
    :param XResourceModule module:
    """
    if not keyisset(module.res_key, settings.compose_content):
        return
    resources_ordered_dict = OrderedDict(
        sorted(
            settings.compose_content[module.res_key].items(),
            key=lambda item: item[0],
        )
    )
    del settings.compose_content[module.res_key]
    settings.compose_content[module.res_key] = resources_ordered_dict
    for resource_name, resource_definition in resources_ordered_dict.items():
        new_definition = resource_class(
            name=resource_name,
            definition=resource_definition,
            module=module,
            settings=settings,
        )
        LOG.debug(type(new_definition))
        LOG.debug(new_definition.__dict__)
        settings.compose_content[module.res_key][resource_name] = new_definition


def get_setting_key(name: str, settings_dict: dict) -> str:
    """
    Allows for flexibility in the syntax, i.e. to make access/Access both valid
    """
    if keyisset(name.title(), settings_dict):
        return name.title()
    return name


def get_top_stack(curr_stack, settings: ComposeXSettings):
    if (
        curr_stack.parent_stack and curr_stack.parent_stack == settings.root_stack
    ) or not curr_stack.parent_stack:
        return curr_stack
    return get_top_stack(curr_stack.parent_stack, settings)
