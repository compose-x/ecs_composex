#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to define the ComposeX Resources into a simple object to make it easier to navigate through.
"""

import json
import re
import warnings
from copy import deepcopy
from os import path
from re import sub

import jsonschema
from compose_x_common.aws import get_account_id
from compose_x_common.compose_x_common import (
    attributes_to_mapping,
    keyisset,
    keypresent,
    set_else_none,
)
from importlib_resources import files as pkg_files
from troposphere import AWSObject, Export, FindInMap, GetAtt, Join, Output, Ref, Sub
from troposphere.ecs import Environment

from ecs_composex.common import LOG, NONALPHANUM, add_parameters
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.rds_resources_settings import handle_new_tcp_resource, import_dbs
from ecs_composex.resource_settings import (
    get_parameter_settings,
    handle_resource_to_services,
    link_resource_to_services,
)

ENV_VAR_NAME = re.compile(r"([^a-zA-Z0-9_]+)")


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


class XResource(object):
    """
    Class to represent each defined resource in the template

    :cvar dict policies_scaffolds: IAM policies template to use to generate IAM policies for the given resource
    :ivar str name: The name of the resource as defined in compose file
    :ivar dict definition: The definition of the resource as defined in compose file
    :ivar str logical_name: Name of the resource to use in CFN template as for export/import
    :ivar bool requires_vpc: Whether or not the resource requires a VPC to function (i.e. RDS)
    """

    policies_scaffolds = {}

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        """
        :param str name: Name of the resource in the template
        :param dict definition: The definition of the resource as-is
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.validate_schema(name, definition, module_name)
        self.name = name
        self.requires_vpc = False
        self.arn = None
        self.cloud_control_attributes_mapping = {}
        self.native_attributes_mapping = {}
        self.module_name = module_name
        self.mapping_key = mapping_key
        if self.mapping_key is None:
            self.mapping_key = self.module_name
        self.definition = deepcopy(definition)
        self.env_names = []
        self.env_vars = []
        self.validators = []
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
        if self.lookup:
            self.lookup_session = define_lookup_role_from_info(
                self.lookup, settings.session
            )
        else:
            self.lookup_session = settings.session
        if keyisset("Properties", self.definition) and not self.lookup:
            self.properties = self.definition["Properties"]
        elif not keyisset("Properties", self.definition) and keypresent(
            "Properties", self.definition
        ):
            self.properties = {}
        else:
            self.properties = None
        self.parameters = (
            {}
            if not keyisset("MacroParameters", self.definition)
            else self.definition["MacroParameters"]
        )
        self.uses_default = not any(
            [self.lookup, self.parameters, self.use, self.properties]
        )
        self.cfn_resource = None
        self.output_properties = {}
        self.outputs = []
        self.attributes_outputs = {}

        self.is_nested = False
        self.stack = None
        self.ref_parameter = None
        self.lookup_properties = {}
        self.mappings = {}
        self.default_tags = {
            "compose-x::module": self.module_name,
            "compose-x::resource_name": self.name,
            "compose-x::logical_name": self.logical_name,
        }
        self.cloudmap_settings = set_else_none("x-cloudmap", self.settings, {})
        self.default_cloudmap_settings = {}
        self.cloudmap_dns_supported = False

    def __repr__(self):
        return self.logical_name

    def validate(self, settings, root_stack=None, *args, **kwargs) -> None:
        """
        Function to implement self-validation for the resource and the execution settings.

        :param settings:
        :param root_stack:
        :param args:
        :param kwargs:
        """

    def validate_schema(self, name, definition, module_name) -> None:
        """
        JSON Validation of the resources module validation
        """

        import json

        RES_KEY = f"{X_KEY}{module_name}"
        module_source = pkg_files("ecs_composex").joinpath(
            f"{module_name}/{RES_KEY}.spec.json"
        )
        try:
            module_schema = json.loads(module_source.read_text())
        except FileNotFoundError:
            LOG.error(
                f"{RES_KEY}.{name} - No module schema found for that resource. Errors might occur!!"
            )
            return
        resolver_source = pkg_files("ecs_composex").joinpath("specs/compose-spec.json")
        LOG.debug(f"Validating against input schema {resolver_source}")
        resolver = jsonschema.RefResolver(
            base_uri=f"file://{path.abspath(path.dirname(resolver_source))}/",
            referrer=module_schema,
        )

        try:
            jsonschema.validate(
                definition,
                module_schema,
                resolver=resolver,
            )
        except jsonschema.exceptions.ValidationError as error:
            LOG.error(f"{RES_KEY}.{name} - Definition is not conform to schema.")
            raise

    def cloud_control_attributes_mapping_lookup(
        self, resource_type, resource_id, **kwargs
    ):
        """
        Method to map the resource properties to the CCAPI description
        :return:
        """
        client = self.lookup_session.client("cloudcontrol")
        try:
            props_r = client.get_resource(
                TypeName=resource_type, Identifier=resource_id, **kwargs
            )
            properties = json.loads(props_r["ResourceDescription"]["Properties"])
            props = attributes_to_mapping(
                properties, self.cloud_control_attributes_mapping
            )
            return props
        except client.exceptions.UnsupportedActionException:
            LOG.warning("Resource not yet supported by Cloud Control API")
            return {}

    def native_attributes_mapping_lookup(self, account_id, resource_id, function):
        properties = function(self, account_id, resource_id)
        if self.native_attributes_mapping:
            conform_mapping = attributes_to_mapping(
                properties, self.native_attributes_mapping
            )
            return conform_mapping
        return properties

    def init_outputs(self):
        """
        Placeholder method
        """
        self.output_properties = {}

    def lookup_resource(
        self,
        arn_re,
        native_lookup_function,
        cfn_resource_type,
        tagging_api_id,
        subattribute_key=None,
    ):
        """
        Method to self-identify properties. It will try to use AWS Cloud Control API if possible, otherwise fallback
        to using boto3 descriptions functions to create a mapping of the attributes.
        """
        self.init_outputs()
        lookup_attributes = self.lookup
        if subattribute_key is not None:
            lookup_attributes = self.lookup[subattribute_key]
        if keyisset("Arn", lookup_attributes):
            LOG.info(f"{self.module_name}.{self.name} - Lookup via ARN")
            LOG.debug(
                f"{self.module_name}.{self.name} - ARN is {lookup_attributes['Arn']}"
            )
            arn_parts = arn_re.match(lookup_attributes["Arn"])
            if not arn_parts:
                raise KeyError(
                    f"{self.module_name}.{self.name} - ARN {lookup_attributes['Arn']} is not valid. Must match",
                    arn_re.pattern,
                )
            self.arn = lookup_attributes["Arn"]
            resource_id = arn_parts.group("id")
            account_id = arn_parts.group("accountid")
        elif keyisset("Tags", lookup_attributes):
            LOG.info(f"{self.module_name}.{self.name} - Lookup via Tags")
            LOG.debug(
                f"{self.module_name}.{self.name} - Lookup tags -> {lookup_attributes}"
            )
            self.arn = find_aws_resource_arn_from_tags_api(
                lookup_attributes, self.lookup_session, tagging_api_id
            )
            arn_parts = arn_re.match(self.arn)
            resource_id = arn_parts.group("id")
            account_id = arn_parts.group("accountid")
        else:
            raise KeyError(
                f"{self.module_name}.{self.name} - You must specify Arn or Tags to identify existing resource"
            )
        if not self.arn:
            raise LookupError(
                f"{self.module_name}.{self.name} - Failed to find the AWS Resource with given tags"
            )
        props = {}
        _account_id = get_account_id(self.lookup_session)
        if _account_id == account_id and self.cloud_control_attributes_mapping:
            props = self.cloud_control_attributes_mapping_lookup(
                cfn_resource_type, resource_id
            )
        if not props:
            props = self.native_attributes_mapping_lookup(
                account_id, resource_id, native_lookup_function
            )
        self.lookup_properties = props
        self.generate_cfn_mappings_from_lookup_properties()
        self.generate_outputs()

    def generate_cfn_mappings_from_lookup_properties(self):
        """
        Sets the .mappings attribute based on the lookup_attributes for CFN purposes
        """
        for parameter, value in self.lookup_properties.items():
            if not isinstance(parameter, Parameter):
                raise TypeError(
                    f"{self.module_name}.{self.name} - lookup attribute {parameter} is",
                    type(parameter),
                    "Expected",
                    Parameter,
                )
            if parameter.return_value:
                self.mappings[NONALPHANUM.sub("", parameter.return_value)] = value
            else:
                self.mappings[parameter.title] = value

    def generate_resource_service_env_vars(
        self, target: tuple, target_definition: dict
    ) -> list:
        """
        Generates env vars based on ReturnValues set for a give service. When the resource is new, adds the
        parameter to the services stack appropriately.
        """
        res_return_names = {}
        for prop_param in self.attributes_outputs.keys():
            if prop_param.return_value:
                res_return_names[prop_param.return_value] = prop_param
            else:
                res_return_names[prop_param.title] = prop_param
        env_vars = []
        params_to_add = []
        if (
            self.ref_parameter
            and self.ref_parameter.title not in target_definition.keys()
        ):
            target_definition[self.ref_parameter.title] = ENV_VAR_NAME.sub(
                "", self.name.replace("-", "_").upper()
            )
        else:
            LOG.info(
                f"{self.module_name}.{self.module_name} - Ref parameter {self.ref_parameter.title} override."
            )
        for prop_name, env_var_name in target_definition.items():
            if prop_name in res_return_names:
                if self.cfn_resource:
                    env_vars.append(
                        Environment(
                            Name=env_var_name,
                            Value=Ref(
                                self.attributes_outputs[res_return_names[prop_name]][
                                    "ImportParameter"
                                ]
                            ),
                        )
                    )
                    params_to_add.append(res_return_names[prop_name])
                elif self.lookup_properties:
                    env_vars.append(
                        Environment(
                            Name=env_var_name,
                            Value=self.attributes_outputs[res_return_names[prop_name]][
                                "ImportValue"
                            ],
                        )
                    )
        if params_to_add:
            params_values = {}
            settings = [get_parameter_settings(self, param) for param in params_to_add]
            resource_params_to_add = []
            for setting in settings:
                resource_params_to_add.append(setting[1])
                params_values[setting[0]] = setting[2]
            add_parameters(target[0].template, resource_params_to_add)
            target[0].stack.Parameters.update(params_values)
        return env_vars

    def generate_ref_env_var(self, target) -> list:
        """
        Method to define all the env var of a resource based on its own defined output attributes
        """
        if not self.ref_parameter:
            LOG.error(
                f"{self.module_name}.{self.name}. Default ref_parameter not set. Skipping env_vars"
            )
            return []
        env_var_name = ENV_VAR_NAME.sub("", self.name.upper().replace("-", "_"))
        if self.cfn_resource and self.attributes_outputs and self.ref_parameter:
            ref_env_var = Environment(
                Name=env_var_name,
                Value=Ref(
                    self.attributes_outputs[self.ref_parameter]["ImportParameter"]
                ),
            )
            ref_param_settings = get_parameter_settings(self, self.ref_parameter)
            add_parameters(target[0].template, [ref_param_settings[1]])
            target[0].stack.Parameters.update(
                {ref_param_settings[0]: ref_param_settings[2]}
            )
        elif self.lookup_properties and self.ref_parameter:
            ref_env_var = Environment(
                Name=env_var_name,
                Value=self.attributes_outputs[self.ref_parameter]["ImportValue"],
            )
        else:
            raise ValueError(
                f"{self.module_name}.{self.name} - Unable to set the default env var"
            )
        return [ref_env_var]

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
                NONALPHANUM.sub("", attribute_parameter.return_value),
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
                Sub(
                    f"${{STACK_NAME}}{DELIM}{self.name}{DELIM}{output_definition[4]}",
                    STACK_NAME=define_stack_name(),
                )
            )
        else:
            export = Export(
                Sub(
                    f"${{STACK_NAME}}{DELIM}{self.logical_name}{DELIM}{attribute_parameter.title}",
                    STACK_NAME=define_stack_name(),
                ),
            )
        return export

    def set_new_resource_outputs(self, output_definition, attribute_parameter):
        """
        Method to define the outputs for the resource when new
        """
        if output_definition[2] is Ref and issubclass(
            type(output_definition[1]), AWSObject
        ):
            value = Ref(output_definition[1])
        elif output_definition[2] is GetAtt:
            value = GetAtt(output_definition[1], output_definition[3])
        elif output_definition[2] is Sub:
            value = Sub(output_definition[3])
        elif output_definition[2] is Join:
            if not isinstance(output_definition[3], list):
                raise ValueError(
                    "For Join, the parameter must be",
                    list,
                    "Got",
                    type(output_definition[3]),
                )
            value = Join(*output_definition[3])
        elif (
            isinstance(output_definition[2], (str, int))
            and output_definition[3] is False
        ):
            value = (
                output_definition[2]
                if isinstance(output_definition[2], str)
                else str(output_definition[2])
            )
        else:
            raise TypeError(
                output_definition,
                f"3rd argument for {output_definition[0]} must be one of",
                (Ref, GetAtt, Sub, Join),
                "Got",
                output_definition[2],
            )
        export = self.define_export_name(output_definition, attribute_parameter)
        return value, export

    def add_new_output_attribute(self, attribute_id, attribute_config):
        """
        Adds a new output to attributes and re-generates all outputs

        :param attribute_id:
        :param tuple attribute_config:
        """
        if not self.output_properties:
            self.output_properties = {attribute_id: attribute_config}
        else:
            self.output_properties.update({attribute_id: attribute_config})
        self.generate_outputs()

    def generate_outputs(self):
        """
        Method to create the outputs for XResources
        """
        if self.stack and not self.stack.is_void:
            root_stack = self.stack.title
        else:
            root_stack = self.mapping_key
        if self.lookup_properties:
            for attribute_parameter, value in self.lookup_properties.items():
                output_name = f"{self.logical_name}{attribute_parameter.title}"
                self.attributes_outputs[attribute_parameter] = {
                    "Name": output_name,
                    "ImportValue": self.set_attributes_from_mapping(
                        attribute_parameter
                    ),
                    "ImportParameter": Parameter(
                        output_name,
                        group_label=attribute_parameter.group_label
                        if attribute_parameter.group_label
                        else self.module_name,
                        return_value=attribute_parameter.return_value,
                        Type=attribute_parameter.Type,
                    ),
                }
        elif self.output_properties and not self.lookup_properties:
            for (
                attribute_parameter,
                output_definition,
            ) in self.output_properties.items():
                output_name = NONALPHANUM.sub("", output_definition[0])
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
                        group_label=attribute_parameter.group_label
                        if attribute_parameter.group_label
                        else self.module_name,
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


class ServicesXResource(XResource):
    """
    Class for XResource that would be linked to services for IAM / Ingress

    :ivar list[tuple] families_targets: List of the service targets to associate access with
    :ivar list[tuple] families_scaling: List of the services target to associate scaling with
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        self.services = []
        self.families_targets = []
        self.families_scaling = []
        self.arn_parameter = None
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.services = (
            []
            if not keyisset("Services", self.definition)
            else self.definition["Services"]
        )
        self.set_services_targets(settings)
        self.set_services_scaling(settings)

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

    def set_services_targets_from_list(self, settings):
        """
        Deals with services set as a list

        :param settings:
        :return:
        """
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
                LOG.debug(
                    f"{self.module_name}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion(service, settings)

    def handle_families_targets_expansion_dict(
        self, service_name, service, settings
    ) -> None:
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param str service_name:
        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        """
        the_service = [s for s in settings.services if s.name == service_name][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [the_service],
                        service["Access"] if keyisset("Access", service) else {},
                        service,
                    )
                )

    def set_services_targets_from_dict(self, settings):
        """
        Deals with services set as a dict

        :param settings:
        :return:
        """
        for service_name, service_def in self.services.items():
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service_def["Access"]
                        if keyisset("Access", service_def)
                        else {},
                        service_def,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.debug(
                    f"{self.module_name}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion_dict(
                    service_name, service_def, settings
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
            LOG.debug(f"{self.module_name}.{self.name} No Services defined.")
            return
        if isinstance(self.services, list):
            self.set_services_targets_from_list(settings)
        elif isinstance(self.services, dict):
            self.set_services_targets_from_dict(settings)
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

    def set_services_scaling_list(self, settings):
        """
        Method to map services and families targets of the services defined.

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services or isinstance(self.services, dict):
            return
        for service in self.services:
            name_key = get_setting_key("name", service)
            scaling_key = get_setting_key("scaling", service)
            if not keyisset(scaling_key, service):
                LOG.debug(
                    f"{self.module_name}.{self.name} - No Scaling set for {service[name_key]}"
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
                LOG.debug(
                    f"{self.module_name}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_family_scaling_expansion(service, settings)

    def handle_families_scaling_expansion_dict(self, service_name, service, settings):
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param str service_name:
        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        """
        the_service = [s for s in settings.services if s.name == service_name][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_scaling]:
                self.families_scaling.append(
                    (
                        settings.families[family_name],
                        service["Scaling"],
                    )
                )

    def set_services_targets_scaling_from_dict(self, settings) -> None:
        """
        Deals with services set as a dict

        :param settings:
        """
        for service_name, service_def in self.services.items():
            if not keyisset("Scaling", service_def):
                LOG.debug(
                    f"{self.module_name}.{self.name} - No Scaling set for {service_name}"
                )
                continue
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_scaling
            ]:
                self.families_scaling.append(
                    (
                        settings.families[service_name],
                        service_def["Scaling"],
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_scaling
            ]:
                LOG.debug(
                    f"{self.module_name}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_scaling_expansion_dict(
                    service_name, service_def, settings
                )

    def set_services_scaling(self, settings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            LOG.debug(f"{self.module_name}.{self.name} No Services defined.")
            return
        if isinstance(self.services, list):
            self.set_services_scaling_list(settings)
        elif isinstance(self.services, dict):
            self.set_services_targets_scaling_from_dict(settings)


class AwsEnvironmentResource(XResource):
    """
    Class for AWS Resources that are used by other AWS Resources. The services do not use these resources directly

    :ivar bool lookup_only: Whether the XResource should only be looked up.
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        self.lookup_only = False
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.requires_vpc = False
        self.arn_parameter = None


class ApiXResource(ServicesXResource):
    """
    Class for Resources that only require API / IAM access to be defined
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.predefined_resource_service_scaling_function = None

    def to_ecs(self, settings, root_stack=None) -> None:
        """
        Maps API only based resource to ECS Services
        """
        LOG.info(f"{self.module_name}.{self.name} - Linking to services")
        handle_resource_to_services(
            settings,
            self,
            arn_parameter=self.arn_parameter,
            nested=False,
        )
        if self.predefined_resource_service_scaling_function:
            self.predefined_resource_service_scaling_function(self, settings)


class NetworkXResource(ServicesXResource):

    """
    Class for resources that need VPC and SecurityGroups to be managed for Ingress
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        self.subnets_override = None
        self.security_group = None
        self.security_group_param = None
        self.port_param = None
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.requires_vpc = True
        self.cleanse_external_targets()
        self.set_override_subnets()
        self.cloudmap_dns_supported = True

    def remove_services_after_family_cleanups(self) -> None:
        """
        After the family services have been removed from the target, we ensure that we deal with the services
        which may or may not be in the targets already
        """
        if isinstance(self.services, list):
            for service in self.services:
                family_name = (
                    service["name"].split(":")[0]
                    if r":" in service["name"]
                    else service["name"]
                )
                for family in self.families_targets:
                    if family[0].name == family_name or family_name in [
                        svc.name for svc in family[0].services
                    ]:
                        break
                else:
                    self.services.remove(service)

        elif isinstance(self.services, dict):
            to_del = []
            for service_name, service in self.services.items():
                family_name = (
                    service_name.split(":")[0] if r":" in service_name else service_name
                )
                for family in self.families_targets:
                    if family[0].name == family_name or family_name in [
                        svc.name for svc in family[0].services
                    ]:
                        break
                else:
                    to_del.append(service_name)
            for key in to_del:
                print(f"{self.module_name}.{self.name} - Removing service {key}")
                del self.services[key]

    def cleanse_external_targets(self) -> None:
        """
        Will automatically remove the target families which are set as external
        """
        for target in self.families_targets:
            if target[0].launch_type and target[0].launch_type == "EXTERNAL":
                LOG.info(
                    f"{self.module_name}.{self.name} - Target {target[0].name} - Launch Type not supported (EXTERNAL)"
                )
                self.families_targets.remove(target)
        for target in self.families_scaling:
            if target[0].launch_type and target[0].launch_type == "EXTERNAL":
                LOG.info(
                    f"{self.module_name}.{self.name} - Target {target[0].name} - Launch Type not supported (EXTERNAL)"
                )
                self.families_scaling.remove(target)
        self.remove_services_after_family_cleanups()

    def set_override_subnets(self) -> None:
        """
        Updates the subnets to use from default for the given resource
        """
        if (
            self.settings
            and keyisset("Subnets", self.settings)
            and hasattr(self, "subnets_param")
        ):
            self.subnets_override = self.settings["Subnets"]
        elif (
            self.parameters
            and keyisset("Subnets", self.parameters)
            and hasattr(self, "subnets_param")
        ):
            self.subnets_override = self.parameters["Subnets"]

    def update_from_vpc(self, vpc_stack, settings=None):
        """
        Allows to make adjustments after the VPC Settings have been set
        """
        pass


class DatabaseXResource(NetworkXResource):
    """
    Class for network resources that share common properties

    :ivar ecs_composex.common.cfn_params.Parameter db_secret_arn_parameter:
    :ivar ecs_composex.common.cfn_params.Parameter db_cluster_endpoint_param:
    """

    def __init__(
        self, name: str, definition: dict, module_name: str, settings, mapping_key=None
    ):
        self.db_secret = None
        self.db_secret_arn_parameter = None
        self.db_cluster_arn_parameter = None
        self.db_cluster_arn = None
        self.db_cluster_endpoint_param = None
        self.db_cluster_ro_endpoint_param = None
        super().__init__(name, definition, module_name, settings, mapping_key)
        self.default_cloudmap_settings = {
            "DnsSettings": {
                "Hostname": self.logical_name,
            },
        }

    def to_ecs(self, settings, root_stack=None) -> None:
        """
        Maps a database service to ECS services

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        """
        if not self.mappings and self.cfn_resource:
            handle_new_tcp_resource(
                self,
                port_parameter=self.port_param,
                sg_parameter=self.security_group_param,
                secret_parameter=self.db_secret_arn_parameter,
            )
            if self.db_cluster_arn_parameter:
                link_resource_to_services(
                    settings,
                    self,
                    arn_parameter=self.db_cluster_arn_parameter,
                    access_subkeys=["DBCluster"],
                )
        elif self.mappings and not self.cfn_resource:
            import_dbs(self, settings)
