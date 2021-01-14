#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

from copy import deepcopy

from troposphere import Output, Parameter, Export
from troposphere import Ref, GetAtt, Sub, If
from troposphere import AWS_STACK_NAME
from troposphere.ecs import Environment


from ecs_composex.common import LOG, NONALPHANUM, keyisset, keypresent
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
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

    policies_scaffolds = {}

    def __init__(self, name, definition, settings):
        """
        Init the class
        :param str name: Name of the resource in the template
        :param dict definition: The definition of the resource as-is
        """
        self.name = name
        self.definition = deepcopy(definition)
        self.env_vars = []
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.settings = (
            None
            if not keyisset("Settings", self.definition)
            else self.definition["Settings"]
        )
        self.use = (
            None if not keyisset("Use", self.definition) else self.definition["Use"]
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
        self.parameters = (
            {}
            if not keyisset("MacroParameters", self.definition)
            else self.definition["MacroParameters"]
        )
        self.cfn_resource = None
        self.output_properties = {}
        self.outputs = []
        self.attributes_outputs = {}
        self.families_targets = []
        self.families_scaling = []
        self.subnets_override = None
        self.arn_attr = None
        self.arn_parameter = None
        self.arn_value = None
        self.ref_value = None
        self.is_nested = False
        self.ref_parameter = Parameter(self.logical_name, Type="String")
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
                        service,
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
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service["access"],
                        service,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.warning(
                    f"The family {service_name} has already been added. Skipping"
                )
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

    def generate_resource_envvars(self, value):
        """
        :return: environment key/pairs
        :rtype: list<troposphere.ecs.Environment>
        """
        if self.settings and keyisset("EnvNames", self.settings):
            for env_name in self.settings["EnvNames"]:
                self.env_vars.append(
                    Environment(
                        Name=env_name,
                        Value=value,
                    )
                )
            if self.name not in self.settings["EnvNames"] and self.name not in [
                var.Name for var in self.env_vars
            ]:
                self.env_vars.append(
                    Environment(
                        Name=self.name,
                        Value=value,
                    )
                )
                if self.name != self.logical_name:
                    self.env_vars.append(
                        Environment(Name=self.logical_name, Value=value)
                    )
        elif (
            not self.settings
            and not keyisset("EnvNames", self.settings)
            and self.name not in [var.Name for var in self.env_vars]
        ):
            self.env_vars.append(
                Environment(
                    Name=self.name,
                    Value=value,
                )
            )
        self.env_vars = list({v.Name: v for v in self.env_vars}.values())

    def generate_outputs(self):
        """
        Method to create the outputs for XResources
        :return:
        """
        for output_prop_name in self.output_properties:
            definition = self.output_properties[output_prop_name]
            if definition[2] is Ref:
                value = Ref(definition[1])
            elif definition[2] is GetAtt:
                value = GetAtt(definition[1], definition[3])
            else:
                raise TypeError(
                    f"3rd argument for {definition[0]} must be one of",
                    (Ref, GetAtt),
                    "Got",
                    definition[2],
                )
            name = NONALPHANUM.sub("", definition[0])
            if len(definition) == 5 and definition[4]:
                LOG.debug(f"Adding portback output for {self.name}")
                export = Export(
                    If(
                        USE_STACK_NAME_CON_T,
                        Sub(
                            f"${{{AWS_STACK_NAME}}}{DELIM}{self.name}{DELIM}{definition[4]}"
                        ),
                        Sub(
                            f"${{{ROOT_STACK_NAME.title}}}{DELIM}{self.name}{DELIM}{definition[4]}"
                        ),
                    )
                )
            else:
                export = Export(
                    If(
                        USE_STACK_NAME_CON_T,
                        Sub(f"${{{AWS_STACK_NAME}}}{DELIM}{name}"),
                        Sub(f"${{{ROOT_STACK_NAME.title}}}{DELIM}{name}"),
                    )
                )
            self.attributes_outputs[output_prop_name] = {
                "Name": name,
                "Output": Output(name, Value=value, Export=export),
            }

        for attr in self.attributes_outputs.values():
            self.outputs.append(attr["Output"])

    def set_resource_arn(self, root_stack_name):
        """
        Method to set the arn value the resource arn to use from root stack to another
        """
        if not isinstance(self.arn_attr, Parameter) or not keyisset(
            self.arn_attr.title, self.output_properties
        ):
            raise KeyError(
                "There is no ARN defined for this resource", self.logical_name
            )
        self.arn_value = GetAtt(
            root_stack_name, f"Outputs.{self.logical_name}{self.arn_attr.title}"
        )

    def set_resource_arn_parameter(self):
        """
        Method to set the ARN parameter to add to consuming stacks
        """
        if not isinstance(self.arn_attr, Parameter) or not keyisset(
            self.arn_attr.title, self.output_properties
        ):
            raise KeyError(
                "Parameter - There is no ARN defined for this resource",
                self.logical_name,
            )
        self.arn_parameter = Parameter(
            f"{self.logical_name}{self.arn_attr.title}", Type="String"
        )

    def set_ref_resource_value(self, root_stack_name):
        """
        Method to set the value for the default attribute (Ref)
        """
        self.ref_value = GetAtt(root_stack_name, f"Outputs.{self.logical_name}")

    def get_resource_attribute_parameter(self, parameter):
        title = parameter.title if isinstance(parameter, Parameter) else parameter
        if not isinstance(parameter, (str, Parameter)) or not keyisset(
            title, self.attributes_outputs
        ):
            raise KeyError(
                "There is no Output attribute defined for",
                self.logical_name,
                "with parameter named",
                parameter.title if isinstance(parameter, Parameter) else parameter,
            )
        return Parameter(f"{self.attributes_outputs[title]['Name']}", Type="String")

    def get_resource_attribute_value(self, parameter, stack_name):
        title = parameter.title if isinstance(parameter, Parameter) else parameter
        if not isinstance(parameter, (str, Parameter)) or not keyisset(
            title, self.attributes_outputs
        ):
            raise KeyError(
                "There is no Output attribute value defined for",
                self.logical_name,
                "with parameter named",
                title,
                "Existing ones are",
                self.attributes_outputs.keys(),
            )
        return GetAtt(stack_name, f"Outputs.{self.attributes_outputs[title]['Name']}")

    def set_override_subnets(self):
        if (
            self.settings
            and keyisset("Subnets", self.settings)
            and hasattr(self, "subnets_param")
        ):
            self.subnets_override = self.settings["Subnets"]
