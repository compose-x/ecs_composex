# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to handle Root stacks and substacks in ECS composeX. Allows to treat everything in memory before uploading
files into S3 and on disk.
"""

from troposphere import Template
from troposphere.cloudformation import Stack

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.files import FileArtifact


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

    def render(self, settings, extension=None, **kwargs):
        """
        Function to use when the template is finalized and can be uploaded to S3.
        """
        if extension is None:
            extension = "yml"
        LOG.debug(f"Rendering {self.title}")
        template_file = FileArtifact(
            file_name=f"{self.title}.{extension}",
            template=self.stack_template,
            settings=settings,
        )
        LOG.debug(kwargs)
        template_file.define_body()
        template_file.transcribe()
        template_file.validate()
        LOG.debug(f"Rendered URL = {template_file.url}")
        setattr(self, "TemplateURL", template_file.url)

    def __init__(self, title, stack_template, parameters=None, **kwargs):
        """
        Class to keep track of the template object along with the stack object it represents.

        :param title: title of the resource in the root template
        :param stack_template: the template object to keep track of
        :param dict parameters: Stack parameters to set
        :param kwargs: kwargs from composex along with the kwargs for the stack
        """

        if not isinstance(stack_template, Template):
            raise TypeError(
                "stack_template is", type(stack_template), "expected", Template
            )
        self.stack_template = stack_template
        if parameters is None:
            self.stack_parameters = {}
        elif not isinstance(parameters, dict):
            raise TypeError("parameters is", type(parameters), "expected", dict)
        stack_kwargs = dict((x, kwargs[x]) for x in self.props.keys() if x in kwargs)
        stack_kwargs.update(
            dict((x, kwargs[x]) for x in self.attributes if x in kwargs)
        )
        super().__init__(title, **stack_kwargs)
        if not hasattr(self, "DependsOn") or not keyisset("DependsOn", kwargs):
            self.DependsOn = []


class XModuleStack(ComposeXStack):
    """
    Class to deal specifically with x-modules root stacks
    """


def render_final_template(root_template, settings, **kwargs):
    """
    Function to go through all stacks of a given template and update the template
    It will recursively render sub stacks defined.

    :param root_template: the root template to iterate over the resources.
    :type root_template: troposphere.Template
    """
    resources = root_template.resources
    for resource_name in resources:
        resource = resources[resource_name]
        if isinstance(resource, (XModuleStack, ComposeXStack)):
            LOG.debug(resource)
            LOG.debug(resource.title)
            render_final_template(resource.stack_template, settings, **kwargs)
            resource.render(settings, **kwargs)
        elif isinstance(resource, Stack):
            LOG.warn(resource_name)
            LOG.warn(resource)
