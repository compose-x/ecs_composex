#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
This module allows managing import of x-resources modules into ecs-composex dynamically and order the resources
processing based on the type of resource this is.

Priority order goes

* AWS Environment resources
* AWS API based resources (purely serverless resources)
* AWS Networking based resources (resources that require VPC)

"""

from __future__ import annotations

import sys
import warnings
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.settings import ComposeXSettings
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
import re
from collections import OrderedDict
from copy import deepcopy
from importlib import import_module
from json import loads

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.common.logging import LOG
from ecs_composex.iam.import_sam_policies import import_and_cleanse_sam_policies


class XResourceModule:
    def __init__(
        self,
        res_key: str,
        x_class,
        posix_path,
        resource_class: Union[
            XResource,
            ServicesXResource,
            ApiXResource,
            AwsEnvironmentResource,
            NetworkXResource,
            DatabaseXResource,
        ] = None,
        definition: dict = None,
    ):
        if definition and not isinstance(definition, dict):
            raise TypeError("The module resources definition must be a dict/mapping")
        self._res_key = res_key
        self._xstack_class = x_class
        self._resource_class = resource_class
        self._stack = None
        self._path = posix_path
        self._mod_policies = {}
        self._json_schema = {}
        self.import_perms_definition()
        self.import_json_schema()
        self._resources: dict = {}
        self._definition: dict = {}
        self._original_definition: dict = {}
        self._mappings: dict = {}
        if definition:
            self.definition = definition
            self._original_definition = deepcopy(definition)

    def __del__(self):
        if hasattr(self, "_resources") and self._resources:
            self._resources.clear()

    @property
    def resource_class(
        self,
    ) -> Union[
        XResource,
        ServicesXResource,
        ApiXResource,
        AwsEnvironmentResource,
        NetworkXResource,
        DatabaseXResource,
    ]:
        return self._resource_class

    @property
    def mappings(self) -> dict:
        _lookup_mappings: dict = {}
        for resource in self.lookup_resources:
            _lookup_mappings[resource.logical_name] = resource.mappings
        return _lookup_mappings

    @property
    def new_resources(self) -> list:
        """
        Function to create a list of new resources. Check if empty resource is supported

        :return: list of resources to create
        :rtype: list[XResource] x_resources:
        """
        new_resources = []
        for resource in self.resources_list:
            if resource.lookup:
                continue
            if resource.uses_default and not resource.support_defaults:
                raise KeyError(
                    f"{resource.module.res_key}.{resource.name} - "
                    "Requires either or both Properties or MacroParameters. Got neither",
                    resource.definition.keys(),
                )
            else:
                new_resources.append(resource)
        return new_resources

    @property
    def lookup_resources(self) -> list:
        """
        :return: list of resources to import from Lookup
        :rtype: list[XResource] x_resources:
        """
        lookup_resources = []
        for resource in self.resources_list:
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

    @property
    def resources(
        self,
    ) -> dict[
        str,
        Union[
            XResource,
            ServicesXResource,
            ApiXResource,
            AwsEnvironmentResource,
            NetworkXResource,
            DatabaseXResource,
        ],
    ]:
        return self._resources

    @property
    def resources_list(
        self,
    ) -> list[
        Union[
            XResource,
            ServicesXResource,
            ApiXResource,
            AwsEnvironmentResource,
            NetworkXResource,
            DatabaseXResource,
        ]
    ]:
        return list(self._resources.values())

    @property
    def definition(self) -> dict:
        return self._definition

    @definition.setter
    def definition(self, definition: dict):
        self._definition = definition

    @property
    def res_key(self):
        return self._res_key

    @property
    def mapping_key(self):
        return NONALPHANUM.sub("", re.sub(X_KEY, "", self._res_key))

    @property
    def mod_key(self):
        return re.sub(X_KEY, "", self._res_key)

    @property
    def stack_class(self):
        return self._xstack_class

    @property
    def path(self):
        return str(self._path)

    @property
    def iam_policies(self) -> dict:
        if not self._mod_policies:
            self.import_perms_definition()
        sam_policies = import_and_cleanse_sam_policies()
        sam_policies.update(self._mod_policies)
        return sam_policies

    @property
    def json_schema(self):
        return self._json_schema

    def __repr__(self):
        return self.res_key

    def import_perms_definition(self):
        perms_file_path = self._path.joinpath(f"{self.mod_key}_perms.json")
        try:
            with open(perms_file_path, encoding="utf-8-sig") as perms_fd:
                self._mod_policies = loads(perms_fd.read())
        except OSError:
            pass

    def import_json_schema(self):
        json_schema_file_path = self._path.joinpath(f"{self.res_key}.spec.json")
        try:
            with open(json_schema_file_path, encoding="utf-8-sig") as json_schema_fd:
                self._json_schema = loads(json_schema_fd.read())
        except OSError:
            LOG.warning(
                f"{self.res_key} - JSON Schema not found for validation. Render may contain errors."
            )
            pass

    def set_resources(self, settings: ComposeXSettings):
        """
        Method to define the ComposeXResource for each service.
        First updates the resources dict

        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        if self._resources:
            warnings.warn("BEFORE SETTINGS RESOURCES, SOME WERE ALREADY FOUND")
            self._resources: dict = {}
        _resources = OrderedDict(
            sorted(
                settings.compose_content[self.res_key].items(),
                key=lambda item: item[0],
            )
        )
        if not self._original_definition:
            self._original_definition = {self.res_key: dict(_resources)}
        for resource_name, resource_definition in _resources.items():
            new_definition = self.resource_class(
                name=resource_name,
                definition=resource_definition,
                module=self,
                settings=settings,
            )
            LOG.debug(type(new_definition))
            LOG.debug(new_definition.__dict__)
            self.resources[resource_name] = new_definition


class ModManager:
    """
    Class to manage the modules
    """

    def __init__(self, settings: ComposeXSettings):
        self.modules = {}
        self.loaded_modules: list = []

        for res_key, res_def in settings.compose_content.items():
            if not res_def:
                continue
            self.load_module(res_key, res_def)

    def __del__(self):
        for module in self.modules.values():
            if module:
                module.resources.clear()
        for module in self.loaded_modules:
            if module in sys.modules:
                del sys.modules[module]
            del module

    def init_mods_resources(self, settings: ComposeXSettings):
        for module in self.modules.values():
            if not module.resource_class or not isinstance(
                settings.compose_content[module.res_key], dict
            ):
                continue
            if module.definition:
                module.set_resources(settings)
            elif keyisset(module.res_key, settings.compose_content):
                module.definition = settings.compose_content[module.res_key]
                module.set_resources(settings)

    def modules_repr(self):
        for key, module in self.modules.items():
            print(
                "Loaded",
                module.res_key,
                module.mod_key,
                module.mapping_key,
                module.path,
            )

    def import_resource_modules(self, res_key: str, module_path: str):
        py_module, mod_x_stack_modules = get_module(module_path)
        if mod_x_stack_modules:
            for module_res_key, module_def in mod_x_stack_modules.items():
                self.modules[module_res_key] = module_def["Module"]
            for module_name, module in self.modules.items():
                if module_name == res_key:
                    self.loaded_modules.append(py_module)
                    return module

    def add_module_from_module_def(self, res_key: str, mod_key: str, module_name: str):
        module_path = f"{module_name}.{mod_key}_module"
        core_module = self.import_resource_modules(res_key, module_path)
        if core_module:
            return core_module

        module_name = f"ecs_composex_{mod_key}"
        extensions_modules_path = f"{module_name}.{mod_key}_module"
        extension_module = self.import_resource_modules(
            res_key, extensions_modules_path
        )
        if extension_module:
            return extension_module

    def load_module(
        self, res_key: str, res_def: Union[dict, bool]
    ) -> Union[XResourceModule, None]:
        if not res_key.startswith(X_KEY):
            return
        mod_key = re.sub(X_KEY, "", res_key)
        module_name = f"ecs_composex.{mod_key}"
        module = self.add_module_from_module_def(res_key, mod_key, module_name)
        if not module:
            LOG.error(f"{res_key} - Unable to load module definition")
            return
        if res_def and isinstance(res_def, dict):
            module.definition = res_def
        self.modules[res_key] = module
        return module


def get_module(module_name) -> tuple:
    """
    Function to get the XResourceModule if it has been defined.

    :return: the_class, maps to the main class for the given x-module
    """
    try:
        res_module = import_module(module_name)
        try:
            module = getattr(res_module, "COMPOSE_X_MODULES")
            return res_module, module
        except AttributeError:
            LOG.debug(f"No {module_name}.COMPOSE_X_MODULES found")
    except AttributeError as error:
        LOG.debug(error)
        return None, None
    except ImportError as error:
        LOG.debug(error)
        return None, None
