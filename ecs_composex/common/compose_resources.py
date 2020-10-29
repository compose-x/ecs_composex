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

from troposphere.ecs import Environment

from ecs_composex.common import LOG, NONALPHANUM, keyisset, keypresent
from ecs_composex.resource_settings import generate_export_strings


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
            resource_name, settings.compose_content[res_key][resource_name], settings
        )
        LOG.debug(type(new_definition))
        LOG.debug(new_definition.__dict__)
        settings.compose_content[res_key][resource_name] = new_definition


def validate_service_definition(service):
    required_keys = ["name", "access"]
    if not set(required_keys).issubset(service):
        raise KeyError(
            "Services definition must contain at least",
            required_keys,
            "Got",
            service.keys(),
        )


class XResource(object):
    """
    Class to represent each defined resource in the template

    :cvar str name: The name of the resource as defined in compose file
    :cvar dict definition: The definition of the resource as defined in compose file
    :cvar str logical_name: Name of the resource to use in CFN template as for export/import
    """

    def __init__(self, name, definition, settings):
        """
        Init the class
        :param str name: Name of the resource in the template
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
        self.lookup = (
            None
            if not keyisset("Lookup", self.definition)
            else self.definition["Lookup"]
        )
        if keyisset("Properties", self.definition) and not self.lookup:
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
        self.use = (
            None if not keyisset("Use", self.definition) else self.definition["Use"]
        )
        self.cfn_resource = None
        self.families_targets = []
        self.families_scaling = []
        self.set_services_targets(settings)
        self.set_services_scaling(settings)

    def __repr__(self):
        return self.logical_name

    def debug_families_targets(self):
        for family in self.families_targets:
            LOG.debug(f"Mapped {family[0].name} to {self.name}.")
            if not family[1] and family[2]:
                LOG.debug(f"Applies to service {family[2]}")
            else:
                LOG.debug(f"Applies to all services of {family[0].name}")

    def handle_families_targets_expansion(self, service, settings):
        the_service = [s for s in settings.services if s.name == service["name"]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [the_service],
                        service["access"],
                    )
                )

    def set_services_targets(self, settings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            LOG.info(f"No services defined for {self.name}")
            return
        for service in self.services:
            validate_service_definition(service)
            service_name = service["name"]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (settings.families[service_name], True, [], service["access"])
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.warn(f"The family {service_name} has already been added. Skipping")
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion(service, settings)
        self.debug_families_targets()

    def handle_family_scaling_expansion(self, service, settings):
        """
        Method to search for the families of given service and add it if not already present

        :param dict service:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        the_service = [s for s in settings.services if s.name == service["name"]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_scaling]:
                self.families_scaling.append(
                    (settings.families[family_name], service["scaling"])
                )

    def set_services_scaling(self, settings):
        """
        Method to map services and families targets of the services defined.

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            return
        for service in self.services:
            if not keyisset("scaling", service):
                LOG.debug(
                    f"No scaling for {service['name']} defined based on {self.name}"
                )
                continue
            service_name = service["name"]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_scaling
            ]:
                self.families_scaling.append(
                    (settings.families[service_name], service["scaling"])
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_scaling
            ]:
                LOG.debug(f"The family {service_name} has already been added. Skipping")
            elif service_name in [s.name for s in settings.services]:
                self.handle_family_scaling_expansion(service, settings)

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
