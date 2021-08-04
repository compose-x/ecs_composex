#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to handle Root stacks and substacks in ECS composeX. Allows to treat everything in memory before uploading
files into S3 and on disk.
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import (
    AWS_STACK_NAME,
    FindInMap,
    GetAtt,
    If,
    ImportValue,
    Join,
    Ref,
    Template,
)
from troposphere.cloudformation import Stack

from ecs_composex.common import LOG, NONALPHANUM, add_parameters, cfn_conditions
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.files import FileArtifact
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS,
    APP_SUBNETS_T,
    PUBLIC_SUBNETS,
    PUBLIC_SUBNETS_T,
    STORAGE_SUBNETS,
    STORAGE_SUBNETS_T,
    VPC_ID,
    VPC_ID_T,
)


def render_codepipeline_config_file(parameters):
    """
    Method to write all the parameters in the AWS CFN Config format for Codepipeline
    :param list parameters:
    :return:
    """
    if not parameters:
        return
    config = {"Parameters": {}, "Tags": {}}

    for param in parameters:
        config["Parameters"].update({param["ParameterKey"]: param["ParameterValue"]})
    return config


class ComposeXStack(Stack, object):
    """
    Class to define a CFN Stack as a composition of its template object, parameters, tags etc.

    :cvar ecs_composex.common.files.FileArtifact template_file: The FileArtifact associated with the stack.
    """

    attributes = [
        "Condition",
        "CreationPolicy",
        "DeletionPolicy",
        "DependsOn",
        "Metadata",
        "UpdatePolicy",
        "UpdateReplacePolicy",
    ]
    is_void = False
    mappings = {}

    def __init__(
        self, name, stack_template, stack_parameters=None, file_name=None, **kwargs
    ):
        """
        Class to keep track of the template object along with the stack object it represents.

        :param title: title of the resource in the root template
        :param stack_template: the template object to keep track of
        :param dict stack_parameters: Stack parameters to set
        :param kwargs: kwargs from composex along with the kwargs for the stack
        """
        self.name = name
        self.parent_stack = None
        title = NONALPHANUM.sub("", self.name)
        self.file_name = file_name if file_name else title
        self.lookup_resources = []
        if not isinstance(stack_template, Template):
            raise TypeError(
                "stack_template is", type(stack_template), "expected", Template
            )
        self.stack_template = stack_template
        if stack_parameters is None:
            self.stack_parameters = {}
        elif not isinstance(stack_parameters, dict):
            raise TypeError("parameters is", type(stack_parameters), "expected", dict)
        stack_kwargs = dict((x, kwargs[x]) for x in self.props.keys() if x in kwargs)
        stack_kwargs.update(
            dict((x, kwargs[x]) for x in self.attributes if x in kwargs)
        )
        if stack_parameters:
            stack_kwargs.update({"Parameters": stack_parameters})
        else:
            stack_kwargs.update({"Parameters": {}})
        super().__init__(title, **stack_kwargs)
        if not hasattr(self, "DependsOn") or not keyisset("DependsOn", kwargs):
            self.DependsOn = []

    def mark_nested_stacks(self):
        """
        Method to go over the stack resources, identify the nested stacks, and set a marker of the parent to them
        """
        if not self.stack_template:
            return
        for resource in self.stack_template.resources.values():
            if issubclass(type(resource), ComposeXStack) or isinstance(
                resource, ComposeXStack
            ):
                resource.parent_stack = self
                resource.mark_nested_stacks()

    def get_top_root_stack(self):
        if self.parent_stack:
            return self.parent_stack.get_top_root_stack()
        else:
            return self

    def add_dependencies(self, dependencies):
        """
        Function to add dependencies to DependsOn
        :return:
        """
        if isinstance(dependencies, str):
            self.DependsOn.append(dependencies)
        elif isinstance(dependencies, list):
            self.DependsOn += dependencies

    def add_parameter(self, parameter):
        """
        Function to add a parameter or set of parameters to the stack
        :param parameter:
        :return:
        """
        if not isinstance(parameter, dict):
            raise TypeError("parameter must be of type", dict, "got", type(parameter))
        self.Parameters.update(parameter)

    def write_config_file(self, settings):
        """
        Method to write the parameters file for the stack. Only uses manual input.
        """
        params = self.render_parameters_list_cfn()
        if not params:
            return
        LOG.debug(f"Rendering {self.title}.params.json")
        file = FileArtifact(
            file_name=f"{self.file_name}.params",
            content=params,
            settings=settings,
            file_format="json",
        )
        config = render_codepipeline_config_file(params)
        file.define_body()
        file.write(settings)
        if settings.upload:
            file.upload(settings)
            LOG.debug(f"Rendered URL = {file.url}")
        config_file = FileArtifact(
            file_name=f"{self.file_name}.config",
            content=config,
            settings=settings,
            file_format="json",
        )
        config_file.define_body()
        config_file.write(settings)
        if settings.upload:
            config_file.upload(settings)
            LOG.debug(f"Rendered URL = {file.url}")

    def render_parameters_list_cfn(self):
        """
        Renders parameters in a CFN parameters config file format

        :return: params
        :rtype: list
        """
        if not hasattr(self, "Parameters"):
            return []
        params = []
        for param_name in self.Parameters.keys():
            LOG.debug(f"{param_name} - {self.Parameters[param_name]}")
            if not isinstance(
                self.Parameters[param_name],
                (Ref, GetAtt, ImportValue, If, Join, type(None)),
            ):
                if isinstance(self.Parameters[param_name], (int, str)):
                    params.append(
                        {
                            "ParameterKey": param_name,
                            "ParameterValue": self.Parameters[param_name],
                        }
                    )
                elif isinstance(self.Parameters[param_name], list):
                    params.append(
                        {
                            "ParameterKey": param_name,
                            "ParameterValue": ",".join(self.Parameters[param_name]),
                        }
                    )
        return params

    def render(self, settings):
        """
        Function to use when the template is finalized and can be uploaded to S3.
        """
        LOG.debug(f"Rendering {self.title}")
        self.DependsOn = list(set(self.DependsOn))
        template_file = FileArtifact(
            file_name=self.file_name,
            template=self.stack_template,
            settings=settings,
            file_format=settings.format,
        )
        template_file.define_body()
        template_file.write(settings)
        setattr(self, "TemplateURL", template_file.file_path)
        if settings.upload:
            template_file.upload(settings)
            setattr(self, "TemplateURL", template_file.url)
            LOG.debug(f"Rendered URL = {template_file.url}")
        template_file.validate(settings)
        self.write_config_file(settings)

    def get_from_vpc_stack(self, vpc_stack, *parameters):
        if isinstance(vpc_stack, ComposeXStack):
            vpc = vpc_stack.title
        elif isinstance(vpc_stack, str):
            vpc = vpc_stack
        else:
            raise TypeError(
                "vpc_stack must be of type", ComposeXStack, str, "got", type(vpc_stack)
            )
        default_parameters = [
            VPC_ID,
            PUBLIC_SUBNETS,
            STORAGE_SUBNETS,
            APP_SUBNETS,
        ]
        if not parameters:
            add_parameters(self.stack_template, default_parameters)
            self.Parameters.update(
                {
                    VPC_ID_T: GetAtt(vpc_stack, f"Outputs.{VPC_ID_T}"),
                    PUBLIC_SUBNETS_T: GetAtt(vpc_stack, f"Outputs.{PUBLIC_SUBNETS_T}"),
                    APP_SUBNETS_T: GetAtt(vpc_stack, f"Outputs.{APP_SUBNETS_T}"),
                    STORAGE_SUBNETS_T: GetAtt(
                        vpc_stack, f"Outputs.{STORAGE_SUBNETS_T}"
                    ),
                }
            )
        else:
            for parameter in parameters:
                self.Parameters.update(
                    {parameter: GetAtt(vpc_stack, f"Outputs.{parameter}")}
                )
        if not hasattr(self, "DependsOn"):
            self.DependsOn = [vpc]
        elif hasattr(self, "DependsOn") and vpc not in getattr(self, "DependsOn"):
            self.DependsOn.append(vpc)

    def no_vpc_parameters(self, settings):
        """
        Method to set the stack parameters when we are not creating a VPC.
        """
        add_parameters(self.stack_template, settings.subnets_parameters)
        add_parameters(self.stack_template, [VPC_ID])
        self.Parameters.update(
            {VPC_ID_T: FindInMap("Network", VPC_ID.title, VPC_ID.title)}
        )
        for subnet_param in settings.subnets_parameters:
            self.Parameters.update(
                {
                    subnet_param.title: Join(
                        ",", FindInMap("Network", subnet_param.title, "Ids")
                    )
                }
            )


def process_stacks(root_stack, settings, is_root=True):
    """
    Function to go through all stacks of a given template and update the template
    It will recursively render sub stacks defined.

    :param root_stack: the root template to iterate over the resources.
    :type root_stack: ecs_composex.common.stacks.ComposeXStack
    :param settings: The settings for execution
    :type settings: ecs_composex.common.settings.ComposeXSettings
    """
    resources = root_stack.stack_template.resources
    for resource_name in resources:
        resource = resources[resource_name]
        if isinstance(resource, ComposeXStack) or issubclass(
            type(resource), ComposeXStack
        ):
            LOG.debug(resource)
            LOG.debug(resource.title)
            process_stacks(resource, settings, is_root=False)
            if is_root:
                resource.Parameters.update({ROOT_STACK_NAME_T: Ref(AWS_STACK_NAME)})
            else:
                resource.Parameters.update(cfn_conditions.pass_root_stack_name())
        elif isinstance(resource, Stack):
            LOG.warning(resource_name)
            LOG.warning(resource)
    root_stack.render(settings)
