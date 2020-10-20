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
Module to define the ComposeX Resources into a simple object to make it easier to navigate through.
"""

from json import dumps

from troposphere import Sub
from troposphere.ecs import Environment

from ecs_composex.common import LOG, NONALPHANUM, keyisset, keypresent
from ecs_composex.resource_settings import generate_export_strings
from ecs_composex.common.cfn_params import ROOT_STACK_NAME


def set_resources(settings, resource_class, res_key):
    """
    Method to define the ComposeXResource for each service.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param resource_class:
    :param str res_key:
    """
    if not keyisset(res_key, settings.compose_content):
        return
    for resource_name in settings.compose_content[res_key]:
        new_definition = resource_class(
            resource_name, settings.compose_content[res_key][resource_name]
        )
        LOG.debug(type(new_definition))
        LOG.debug(new_definition.__dict__)
        settings.compose_content[res_key][resource_name] = new_definition


class Service(object):
    """
    Class to represent a service

    :cvar str container_name: name of the container to use in definitions
    """

    main_key = "services"

    def __init__(self, name, definition):
        self.name = name
        self.definition = definition
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.container_name = name
        self.service_name = Sub(f"${{{ROOT_STACK_NAME.title}}}-{self.name}")
        self.cfn_resource = None
        self.secrets = (
            definition["secrets"] if keyisset("secrets", self.definition) else None
        )
        self.volumes = []

    def __repr__(self):
        return self.name


class Volume(object):
    """
    Class to keep track of the Docker-compose Volumes
    """

    main_key = "volumes"
    driver_opts_key = "driver_opts"

    def __init__(self, name, definition):
        self.name = name
        self.volume_name = name
        self.efs_volume = (
            definition["x-efs"]
            if keyisset("x-efs", definition) and isinstance(definition["x-efs"], str)
            else None
        )
        self.device = None
        self.cfn_fs = None
        self.cfn_ap = None
        self.type = "local" if not self.efs_volume else "nfs"

        if (
            keyisset(self.driver_opts_key, definition)
            and isinstance(definition[self.driver_opts_key], dict)
            and keyisset("type", definition[self.driver_opts_key])
            and isinstance(definition[self.driver_opts_key]["type"], str)
            and definition[self.driver_opts_key]["type"] == "nfs"
        ):
            self.type = "efs"
            if keyisset("device", definition[self.driver_opts_key]):
                self.root_folder = definition[self.driver_opts_key]["device"]
            if keyisset("o", definition[self.driver_opts_key]):
                self.mount_options_raw = definition[self.driver_opts_key]["o"]

    def __repr__(self):
        return dumps(
            {"name": self.name, "efs": self.efs_volume, "type": self.type}, indent=4
        )


class XResource(object):
    """
    Class to represent each defined resource in the template

    :cvar str name: The name of the resource as defined in compose file
    :cvar dict definition: The definition of the resource as defined in compose file
    :cvar str logical_name: Name of the resource to use in CFN template as for export/import
    """

    def __init__(self, name, definition):
        """
        Init the class
        :param str name: Name of the resource in the template
        :param str resource_type: The category of resource.
        :param dict definition: The definition of the resource as-is
        """
        self.name = name
        self.definition = definition
        self.env_vars = []
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.settings = (
            None
            if not keyisset("Settings", self.definition)
            else self.definition["Settings"]
        )
        if keyisset("Properties", self.definition):
            self.properties = self.definition["Properties"]
        elif not keyisset("Properties", self.definition) and keypresent(
            "Properties", self.definition
        ):
            self.properties = {}
        else:
            self.properties = None
        self.services = (
            []
            if not keyisset("Services", self.definition)
            else self.definition["Services"]
        )
        self.lookup = (
            None
            if not keyisset("Lookup", self.definition)
            else self.definition["Lookup"]
        )
        self.use = (
            None if not keyisset("Use", self.definition) else self.definition["Use"]
        )
        self.cfn_resource = None

    def __repr__(self):
        return self.logical_name

    def generate_resource_envvars(self, attribute, arn=None):
        """
        :return: environment key/pairs
        :rtype: list<troposphere.ecs.Environment>
        """
        export_string = (
            generate_export_strings(self.logical_name, attribute) if not arn else arn
        )
        if self.settings and keyisset("EnvNames", self.settings):
            for env_name in self.settings["EnvNames"]:
                self.env_vars.append(
                    Environment(
                        Name=env_name,
                        Value=export_string,
                    )
                )
            if self.name not in self.settings["EnvNames"] and self.name not in [
                var.Name for var in self.env_vars
            ]:
                self.env_vars.append(
                    Environment(
                        Name=self.name,
                        Value=export_string,
                    )
                )
                if self.name != self.logical_name:
                    self.env_vars.append(
                        Environment(Name=self.logical_name, Value=export_string)
                    )
        elif (
            not self.settings
            and not keyisset("EnvNames", self.settings)
            and self.name not in [var.Name for var in self.env_vars]
        ):
            self.env_vars.append(
                Environment(
                    Name=self.name,
                    Value=export_string,
                )
            )


class Topic(XResource):
    """
    Class for SNS Topics
    """


class Subscrition(XResource):
    """
    Class for SNS Subscriptions
    """
