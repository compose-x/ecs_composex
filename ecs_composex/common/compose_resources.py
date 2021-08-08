#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to define the ComposeX Resources into a simple object to make it easier to navigate through.
"""

from copy import deepcopy
from re import sub

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import AWS_STACK_NAME, Export, FindInMap, GetAtt, If, Output, Ref, Sub
from troposphere.ecs import Environment

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, Parameter
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common.ecs_composex import X_KEY


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


def get_parameter_settings(resource, parameter):
    """
    Function to define a set of values for the purpose of exposing resources settings from their stack to another.

    :param resource: The XResource we want to extract the outputs from
    :param parameter: The parameter we want to extract the outputs for
    :return: Ordered combination of settings
    :rtype: tuple
    """
    return (
        resource.attributes_outputs[parameter]["Name"],
        resource.attributes_outputs[parameter]["ImportParameter"],
        resource.attributes_outputs[parameter]["ImportValue"],
        parameter,
    )


def get_setting_key(name, settings_dict):
    if keyisset(name.title(), settings_dict):
        return name.title()
    return name


class XResource(object):
    """
    Class to represent each defined resource in the template

    :cvar str name: The name of the resource as defined in compose file
    :cvar dict definition: The definition of the resource as defined in compose file
    :cvar str logical_name: Name of the resource to use in CFN template as for export/import
    """

    policies_scaffolds = {}

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        """
        Init the class
        :param str name: Name of the resource in the template
        :param dict definition: The definition of the resource as-is
        """
        self.name = name
        self.module_name = module_name
        self.mapping_key = mapping_key
        if self.mapping_key is None:
            self.mapping_key = self.module_name
        self.definition = deepcopy(definition)
        self.env_names = []
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
        self.is_nested = False
        self.stack = None
        self.init_env_names()
        self.ref_parameter = Parameter(self.logical_name, Type="String")
        self.set_services_targets(settings)
        self.set_services_scaling(settings)
        self.mappings = {}

    def __repr__(self):
        return self.logical_name

    def debug_families_targets(self):
        """
        Method to troubleshoot family and service mapping
        """
        for family in self.families_targets:
            LOG.debug(f"Mapped {family[0].name} to {self.name}.")
            if not family[1] and family[2]:
                LOG.debug(f"Applies to service {family[2]}")
            else:
                LOG.debug(f"Applies to all services of {family[0].name}")

    def handle_families_targets_expansion(self, service, settings):
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        """
        name_key = get_setting_key("name", service)
        access_key = get_setting_key("access", service)
        the_service = [s for s in settings.services if s.name == service[name_key]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [the_service],
                        service[access_key],
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
            LOG.debug(f"No services defined for {self.name}")
            return
        for service in self.services:
            name_key = get_setting_key("name", service)
            access_key = get_setting_key("access", service)
            service_name = service[name_key]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service[access_key],
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
        name_key = get_setting_key("name", service)
        scaling_key = get_setting_key("scaling", service)
        the_service = [s for s in settings.services if s.name == service[name_key]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_scaling]:
                self.families_scaling.append(
                    (settings.families[family_name], service[scaling_key])
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
            name_key = get_setting_key("name", service)
            scaling_key = get_setting_key("scaling", service)
            if not keyisset(scaling_key, service):
                LOG.debug(
                    f"No scaling for {service[name_key]} defined based on {self.name}"
                )
                continue
            service_name = service[name_key]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_scaling
            ]:
                self.families_scaling.append(
                    (settings.families[service_name], service[scaling_key])
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_scaling
            ]:
                LOG.debug(f"The family {service_name} has already been added. Skipping")
            elif service_name in [s.name for s in settings.services]:
                self.handle_family_scaling_expansion(service, settings)

    def init_env_names(self, add_self_default=True):
        """
        Method to define the environment variables for the resource

        :return: list of environment variable names
        :rtype: list
        """
        if add_self_default:
            self.env_names.append(self.name.replace("-", "_"))
        if (
            self.settings
            and keyisset("EnvNames", self.settings)
            and isinstance(self.settings["EnvNames"], list)
        ):
            for env_name in self.settings["EnvNames"]:
                if isinstance(env_name, str) and env_name not in self.env_names:
                    self.env_names.append(env_name)

    def define_ref_env_vars(self, env_name, parameter):
        """
        Method to define construct parameters for Environment Variable for default Ref value of resource

        :param str env_name:
        :param ecs_composex.common.cfn_params.Parameter parameter:
        :return: dict with the Name and Value for environment variable
        :rtype: dict
        """
        container_env_name = env_name
        if self.lookup:
            container_env_value = self.attributes_outputs[parameter]["ImportValue"]
        else:
            container_env_value = Ref(
                self.attributes_outputs[parameter]["ImportParameter"]
            )
        return {"Name": container_env_name, "Value": container_env_value}

    def define_return_value_env_vars(self, env_name, parameter):
        """
        Method to define construct parameters for Environment Variable for parameters with specific return_value

        :param str env_name:
        :param ecs_composex.common.cfn_params.Parameter parameter:
        :return: dict with the Name and Value for environment variable
        :rtype: dict
        """
        container_env_name = f"{env_name}_{parameter.return_value}"
        if self.lookup:
            container_env_value = Sub(
                f"${{ResourceName}}_{parameter.return_value}",
                ResourceName=self.attributes_outputs[parameter]["ImportValue"],
            )
        else:
            container_env_value = Ref(
                self.attributes_outputs[parameter]["ImportParameter"]
            )
        return {"Name": container_env_name, "Value": container_env_value}

    def generate_resource_envvars(self):
        """
        Method to define all the env var of a resource based on its own defined output attributes
        """
        for env_name in self.env_names:
            if self.cfn_resource:
                for parameter in self.output_properties.keys():
                    if parameter.return_value:
                        env_var = Environment(
                            **self.define_return_value_env_vars(env_name, parameter)
                        )
                    else:
                        env_var = Environment(
                            **self.define_ref_env_vars(env_name, parameter)
                        )
                    self.env_vars.append(env_var)
            elif not self.cfn_resource and self.mappings:
                for key in self.mappings.keys():
                    env_var = Environment(
                        Name=env_name
                        if key == self.logical_name
                        else f"{env_name}_{key}",
                        Value=FindInMap(self.mapping_key, self.logical_name, key),
                    )
                    self.env_vars.append(env_var)
        self.env_vars = list({v.Name: v for v in self.env_vars}.values())

    def set_attributes_from_mapping(self, attribute_parameter):
        """
        Method to define the attribute outputs for lookup resources, which use FindInMap or Ref

        :param attribute_parameter: The parameter mapped to the resource attribute
        :type attribute_parameter: ecs_composex.common.cfn_params.Parameter
        :return: The FindInMap setting for mapped resource
        """
        if attribute_parameter.return_value:
            return FindInMap(
                self.mapping_key,
                self.logical_name,
                attribute_parameter.return_value,
            )
        else:
            return FindInMap(
                self.mapping_key, self.logical_name, attribute_parameter.title
            )

    def define_export_name(self, output_definition, attribute_parameter):
        """
        Method to define the export name for the resource
        :return:
        """
        if len(output_definition) == 5 and output_definition[4]:
            LOG.debug(f"Adding portback output for {self.name}")
            export = Export(
                If(
                    USE_STACK_NAME_CON_T,
                    Sub(
                        f"${{{AWS_STACK_NAME}}}{DELIM}{self.name}{DELIM}{output_definition[4]}"
                    ),
                    Sub(
                        f"${{{ROOT_STACK_NAME.title}}}{DELIM}{self.name}{DELIM}{output_definition[4]}"
                    ),
                )
            )
        else:
            export = Export(
                If(
                    USE_STACK_NAME_CON_T,
                    Sub(
                        f"${{{AWS_STACK_NAME}}}{DELIM}{self.logical_name}{DELIM}{attribute_parameter.title}"
                    ),
                    Sub(
                        f"${{{ROOT_STACK_NAME.title}}}{DELIM}{self.logical_name}{DELIM}{attribute_parameter.title}"
                    ),
                )
            )
        return export

    def set_new_resource_outputs(self, output_definition, attribute_parameter):
        """
        Method to define the outputs for the resource when new
        """
        if output_definition[2] is Ref:
            value = Ref(output_definition[1])
        elif output_definition[2] is GetAtt:
            value = GetAtt(output_definition[1], output_definition[3])
        elif output_definition[2] is Sub:
            value = Sub(output_definition[3])
        else:
            raise TypeError(
                f"3rd argument for {output_definition[0]} must be one of",
                (Ref, GetAtt, Sub),
                "Got",
                output_definition[2],
            )
        export = self.define_export_name(output_definition, attribute_parameter)
        return value, export

    def generate_outputs(self):
        """
        Method to create the outputs for XResources
        """
        if self.stack and not self.stack.is_void:
            root_stack = self.stack.title
        else:
            root_stack = self.mapping_key
        for (
            attribute_parameter,
            output_definition,
        ) in self.output_properties.items():
            output_name = f"{self.logical_name}{attribute_parameter.title}"
            if self.lookup:
                self.attributes_outputs[attribute_parameter] = {
                    "Name": output_name,
                    "ImportValue": self.set_attributes_from_mapping(
                        attribute_parameter
                    ),
                    "ImportParameter": None,
                }
            else:
                settings = self.set_new_resource_outputs(
                    output_definition, attribute_parameter
                )
                value = settings[0]
                export = settings[1]
                self.attributes_outputs[attribute_parameter] = {
                    "Name": output_name,
                    "Output": Output(output_name, Value=value, Export=export),
                    "ImportParameter": Parameter(
                        output_name,
                        return_value=attribute_parameter.return_value,
                        Type=attribute_parameter.Type,
                    ),
                    "ImportValue": GetAtt(
                        root_stack,
                        f"Outputs.{output_name}",
                    ),
                    "Original": attribute_parameter,
                }
        for attr in self.attributes_outputs.values():
            if keyisset("Output", attr):
                self.outputs.append(attr["Output"])

    def set_override_subnets(self):
        if (
            self.settings
            and keyisset("Subnets", self.settings)
            and hasattr(self, "subnets_param")
        ):
            self.subnets_override = self.settings["Subnets"]
