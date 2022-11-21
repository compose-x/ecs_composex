# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to define the ComposeX Resources into a simple object to make it easier to navigate through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

import json
import re
from copy import deepcopy
from os import path

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

from ecs_composex.common import NONALPHANUM, get_nested_property
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import CFN_EXPORT_DELIMITER as DELIM
from ecs_composex.common.ecs_composex import TAGS_SEPARATOR, X_KEY
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_parameters,
    add_update_mapping,
    add_update_parameter_recursively,
)
from ecs_composex.mods_manager import XResourceModule
from ecs_composex.resource_settings import get_parameter_settings

ENV_VAR_NAME = re.compile(r"([^a-zA-Z0-9_]+)")


class XResource:
    """
    Class to represent each defined resource in the template

    :cvar dict policies_scaffolds: IAM policies template to use to generate IAM policies for the given resource
    :ivar str name: The name of the resource as defined in compose file
    :ivar dict definition: The definition of the resource as defined in compose file
    :ivar str logical_name: Name of the resource to use in CFN template as for export/import
    :ivar bool requires_vpc: Whether or not the resource requires a VPC to function (i.e. RDS)
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        """
        :param str name: Name of the resource in the template
        :param dict definition: The definition of the resource as-is
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        if not isinstance(module, XResourceModule):
            raise TypeError(
                name, "module must be", XResourceModule, "Got", module, type(module)
            )
        self.module = module
        self.validate_schema(name, definition, module.mod_key)
        self.name = name
        self.requires_vpc = False
        self.arn = None
        self.iam_manager = None
        self.cloud_control_attributes_mapping = {}
        self.native_attributes_mapping = {}
        self.definition = deepcopy(definition)
        self.env_names = []
        self.env_vars = []
        self.validators = []
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.settings = set_else_none("Settings", definition, alt_value={})
        self.parameters = set_else_none("MacroParameters", definition, alt_value={})
        self.lookup = set_else_none("Lookup", definition, alt_value={})
        if self.lookup:
            self.lookup_session = define_lookup_role_from_info(
                self.lookup, settings.session
            )
            self.properties = {}
        else:
            self.lookup_session = settings.session
            self.properties = set_else_none("Properties", definition)
        self.support_defaults: bool = False
        self.scaling = set_else_none("Scaling", self.definition)
        self.scaling_target = None
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
            f"compose-x{TAGS_SEPARATOR}module": self.module.mod_key,
            f"compose-x{TAGS_SEPARATOR}resource_name": self.name,
            f"compose-x{TAGS_SEPARATOR}logical_name": self.logical_name,
        }
        self.cloudmap_settings = set_else_none("x-cloudmap", self.settings, {})
        self.default_cloudmap_settings = {}
        self.cloudmap_dns_supported = False
        self.policies_scaffolds = module.iam_policies
        self.resource_policy = None

    def __repr__(self):
        return self.logical_name

    @property
    def uses_default(self) -> bool:
        return not any([self.lookup, self.parameters, self.properties])

    @property
    def env_var_prefix(self) -> str:
        return ENV_VAR_NAME.sub("", self.name.replace("-", "_").upper())

    @property
    def compose_x_arn(self) -> str:
        return f"{self.module.res_key}::{self.name}"

    @property
    def property_to_parameter_mapping(self):
        mapping = {}
        if not self.attributes_outputs:
            return mapping
        for parameter in self.output_properties:
            if parameter.return_value:
                mapping[parameter.return_value] = parameter
            else:
                mapping[parameter.title] = parameter
        return mapping

    @property
    def mod_res_key(self) -> str:
        return self.module.res_key

    @property
    def mod_mapping_key(self) -> str:
        return self.module.mapping_key

    def validate(self, settings, root_stack=None, *args, **kwargs) -> None:
        """
        Function to implement self-validation for the resource and the execution settings.

        :param settings:
        :param root_stack:
        :param args:
        :param kwargs:
        """

    def validate_schema(
        self, name, definition, module_name, module_schema: str = None
    ) -> None:
        """
        JSON Validation of the resources module validation
        """
        if not self.module.json_schema and not module_schema:
            return
        resolver_source = pkg_files("ecs_composex").joinpath("specs/compose-spec.json")
        LOG.debug(f"Validating against input schema {resolver_source}")
        resolver = jsonschema.RefResolver(
            base_uri=f"file://{path.abspath(path.dirname(resolver_source))}/",
            referrer=self.module.json_schema,
        )
        try:
            jsonschema.validate(
                definition,
                module_schema if module_schema else self.module.json_schema,
                resolver=resolver,
            )
        except jsonschema.exceptions.ValidationError:
            LOG.error(f"{module_name}.{name} - Definition is not conform to schema.")
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
        use_arn_for_id: bool = False,
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
            LOG.info(f"{self.module.res_key}.{self.name} - Lookup via ARN")
            LOG.debug(
                f"{self.module.res_key}.{self.name} - ARN is {lookup_attributes['Arn']}"
            )
            arn_parts = arn_re.match(lookup_attributes["Arn"])
            if not arn_parts:
                raise KeyError(
                    f"{self.module.res_key}.{self.name} - ARN {lookup_attributes['Arn']} is not valid. Must match",
                    arn_re.pattern,
                )
            self.arn = lookup_attributes["Arn"]
            resource_id = arn_parts.group("id")
            account_id = arn_parts.group("accountid")
        elif keyisset("Tags", lookup_attributes):
            LOG.info(f"{self.module.res_key}.{self.name} - Lookup via Tags")
            LOG.debug(
                f"{self.module.res_key}.{self.name} - Lookup tags -> {lookup_attributes}"
            )
            self.arn = find_aws_resource_arn_from_tags_api(
                lookup_attributes, self.lookup_session, tagging_api_id
            )
            arn_parts = arn_re.match(self.arn)
            resource_id = arn_parts.group("id")
            account_id = arn_parts.group("accountid")
        else:
            raise KeyError(
                f"{self.module.res_key}.{self.name} - You must specify Arn or Tags to identify existing resource"
            )
        if not self.arn:
            raise LookupError(
                f"{self.module.res_key}.{self.name} - Failed to find the AWS Resource with given tags"
            )
        props = {}
        _account_id = get_account_id(self.lookup_session)
        if _account_id == account_id and self.cloud_control_attributes_mapping:
            props = self.cloud_control_attributes_mapping_lookup(
                cfn_resource_type, self.arn if use_arn_for_id else resource_id
            )
        if not props:
            props = self.native_attributes_mapping_lookup(
                account_id,
                self.arn if use_arn_for_id else resource_id,
                native_lookup_function,
            )
        self.lookup_properties = props
        self.generate_cfn_mappings_from_lookup_properties()
        self.generate_outputs()

    def generate_cfn_mappings_from_lookup_properties(self):
        """
        Sets the .mappings attribute based on the lookup_attributes for CFN purposes
        """
        for parameter, value in self.lookup_properties.items():
            print("PARM?", parameter)
            if not isinstance(parameter, Parameter):
                raise TypeError(
                    f"{self.module.res_key}.{self.name} - lookup attribute {parameter} is",
                    parameter,
                    type(parameter),
                    "Expected",
                    Parameter,
                )
            if parameter.return_value:
                if parameter.return_value not in self.mappings:
                    self.mappings[NONALPHANUM.sub("", parameter.return_value)] = value
                else:
                    self.mappings[
                        parameter.title + NONALPHANUM.sub("", parameter.return_value)
                    ] = value
            else:
                self.mappings[parameter.title] = value

    def set_update_container_env_var(
        self, target: tuple, parameter, env_var_name: str
    ) -> list:
        """
        Function that will set or update the value of a given env var from Return value of a resource.
        :param tuple target:
        :param parameter:
        """
        if isinstance(parameter, str):
            try:
                attr_parameter = self.property_to_parameter_mapping[parameter]
            except KeyError:
                LOG.error(
                    f"{self.module.res_key}.{self.name} - No return value {parameter} available."
                )
                return []
        elif isinstance(parameter, Parameter):
            attr_parameter = parameter
        else:
            raise TypeError(
                "parameter is", type(parameter), "must be one of", [str, Parameter]
            )
        env_vars = []
        params_to_add = []
        attr_id = self.attributes_outputs[attr_parameter]
        if self.cfn_resource:
            env_vars.append(
                Environment(
                    Name=env_var_name,
                    Value=Ref(attr_id["ImportParameter"]),
                )
            )
            params_to_add.append(attr_parameter)
        elif self.lookup_properties:
            env_vars.append(
                Environment(
                    Name=env_var_name,
                    Value=attr_id["ImportValue"],
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
        if self.ref_parameter and self.ref_parameter.title in target_definition.keys():
            LOG.debug(
                f"{self.module.res_key}.{self.module.res_key} - Ref parameter {self.ref_parameter.title} override."
            )
        elif (
            self.ref_parameter
            and self.ref_parameter.title not in target_definition.keys()
        ):
            env_var_name = ENV_VAR_NAME.sub("", self.name.replace("-", "_").upper())
            target_definition[self.ref_parameter.title] = env_var_name
            LOG.info(
                f"{self.module.res_key}.{self.name} - Auto-added {env_var_name} for Ref value"
            )
        else:
            LOG.warning(
                f"{self.module.res_key}.{self.name} - Ref parameter not defined on {self.__class__}"
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
                f"{self.module.res_key}.{self.name}. Default ref_parameter not set. Skipping env_vars"
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
                f"{self.module.res_key}.{self.name} - Unable to set the default env var"
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
            long_name = attribute_parameter.title + NONALPHANUM.sub(
                "", attribute_parameter.return_value
            )
        else:
            long_name = attribute_parameter.title
        if self.mappings and long_name in self.mappings:
            return FindInMap(self.module.mapping_key, self.logical_name, long_name)
        elif attribute_parameter.return_value:
            return FindInMap(
                self.module.mapping_key,
                self.logical_name,
                NONALPHANUM.sub("", attribute_parameter.return_value),
            )
        else:
            return FindInMap(
                self.module.mapping_key, self.logical_name, attribute_parameter.title
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
                        else self.module.mod_key,
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
                        else self.module.mod_key,
                        return_value=attribute_parameter.return_value,
                        Type=attribute_parameter.Type,
                    ),
                    "ImportValue": GetAtt(
                        self.stack.get_top_root_stack()
                        if self.stack
                        else self.module.mapping_key,
                        f"Outputs.{output_name}",
                    ),
                    "Original": attribute_parameter,
                }
        for attr in self.attributes_outputs.values():
            if keyisset("Output", attr):
                self.outputs.append(attr["Output"])

    def add_parameter_to_family_stack(
        self, family, settings: ComposeXSettings, parameter: Union[str, Parameter]
    ) -> dict:
        if self.stack == family.stack:
            LOG.warning(
                "Cannot add parameter to resource",
                f"{self.name}",
                "because it is in the same stack as family",
                "{family.name}",
            )
            return self
        if (
            isinstance(parameter, str)
            and parameter in self.property_to_parameter_mapping.keys()
        ):
            the_parameter = self.property_to_parameter_mapping[parameter]
        elif (
            isinstance(parameter, Parameter)
            and parameter in self.property_to_parameter_mapping.values()
        ):
            the_parameter = parameter
        else:
            raise TypeError(
                "parameter must be one of", str, Parameter, "got", type(parameter)
            )

        if self.mappings and self.lookup:
            add_update_mapping(
                family.template,
                self.module.mapping_key,
                settings.mappings[self.module.mapping_key],
            )
            return self.attributes_outputs[the_parameter]

        param_id = self.attributes_outputs[the_parameter]
        add_parameters(family.template, [param_id["ImportParameter"]])
        family.stack.Parameters.update(
            {param_id["ImportParameter"].title: param_id["ImportValue"]}
        )
        return param_id

    def add_attribute_to_another_stack(
        self, ext_stack, attribute: Parameter, settings: ComposeXSettings
    ):

        attr_id = self.attributes_outputs[attribute]
        if self.mappings and self.lookup:
            add_update_mapping(
                ext_stack.stack_template, self.module.mapping_key, self.module.mappings
            )
        elif self.cfn_resource:
            add_update_parameter_recursively(ext_stack, settings, attr_id)
        else:
            raise AttributeError(
                self.module.res_key, self.name, "No lookup nor mappings ??"
            )
        return attr_id

    def post_processing(self, settings: ComposeXSettings):
        if not self.cfn_resource or not hasattr(self, "post_processing_properties"):
            LOG.debug("Not a new cluster or no post_processing_properties. Skipping")
            return
        LOG.info(f"Post processing {self.module.res_key}.{self.name}")
        for _property in self.post_processing_properties:
            cluster_property, property_name, value = get_nested_property(
                self.cfn_resource, _property
            )
            if not value or not isinstance(value, (str, list)):
                continue
            if (
                isinstance(value, list)
                and value
                and isinstance(value[0], str)
                and value[0].startswith(X_KEY)
            ):
                value = value[0]
            if not value.startswith(X_KEY):
                continue
            resource, parameter = settings.get_resource_attribute(value)
            if not resource or not parameter:
                LOG.error(
                    f"Failed to find resource/attribute for {property_name} with value {value}"
                )
                continue
            res_param_id = resource.add_attribute_to_another_stack(
                self.stack, parameter, settings
            )
            if res_param_id is resource:
                res_propery_value = Ref(resource.cfn_resource)
            elif res_param_id is not resource and resource.cfn_resource:
                res_propery_value = Ref(res_param_id["ImportParameter"])
            else:
                res_propery_value = res_param_id["ImportValue"]
            setattr(cluster_property, property_name, res_propery_value)
            LOG.info(
                f"{self.module.res_key}.{self.name}"
                f" - Successfully mapped {_property} to {resource.module.res_key}.{resource.name}",
            )
