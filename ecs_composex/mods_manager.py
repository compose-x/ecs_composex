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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

import re
from importlib import import_module
from json import loads

from importlib_resources import files as pkg_files

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.iam.import_sam_policies import import_and_cleanse_sam_policies


class XResourceModule:
    def __init__(self, res_key: str, x_class, posix_path):
        self._res_key = res_key
        self._xstack_class = x_class
        self._path = posix_path
        self._mod_policies = {}
        self._json_schema = {}
        self.import_perms_definition()
        self.import_json_schema()

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
            pass


class ModManager:
    """
    Class to manage the modules
    """

    def __init__(self, settings: ComposeXSettings):
        self.modules = {}

        for res_key, res_def in settings.compose_content.items():
            if not res_def:
                continue
            self.add_module(res_key)

    def modules_repr(self):
        for key, module in self.modules.items():
            print(
                "Loaded",
                module.res_key,
                module.mod_key,
                module.mapping_key,
                module.path,
            )

    def add_module(self, res_key):
        if not res_key.startswith(X_KEY):
            return
        mod_key = re.sub(X_KEY, "", res_key)
        module_name = f"ecs_composex.{mod_key}"

        mod_x_stack_module = get_module(f"{module_name}.{mod_key}_module")
        if mod_x_stack_module:
            self.modules[res_key] = mod_x_stack_module
            return mod_x_stack_module

        mod_x_stack_class = get_mod_class(f"{module_name}.{mod_key}_stack")
        if not mod_x_stack_class:
            module_name = f"ecs_composex_{mod_key}"
            mod_x_stack_class = get_mod_class(f"{module_name}.{mod_key}_stack")

        if mod_x_stack_class:
            module = XResourceModule(
                res_key,
                mod_x_stack_class,
                pkg_files(module_name),
            )
            self.modules[res_key] = module
            return module


def get_mod_class(module_name):
    """
    Function to get the XModule class for a specific ecs_composex module

    :return: the_class, maps to the main class for the given x-module
    """
    try:
        res_module = import_module(module_name)
        try:
            the_class = getattr(res_module, "XStack")
            return the_class
        except AttributeError as error:
            LOG.debug(error)
            return None
    except ImportError as error:
        LOG.debug(error)
        return None


def get_module(module_name):
    """
    Function to get the XResourceModule if it has been defined.

    :return: the_class, maps to the main class for the given x-module
    """
    try:
        res_module = import_module(module_name)
        try:
            try:
                module = getattr(res_module, "COMPOSE_X_MODULE")
                return module
            except AttributeError:
                LOG.debug(f"No {module_name}.COMPOSE_X_MODULE function found")
        except AttributeError as error:
            LOG.debug(error)
            return None
    except ImportError as error:
        LOG.debug(error)
        return None
