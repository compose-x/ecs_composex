# -*- coding: utf-8 -*-

from troposphere.cloudformation import Stack

from ecs_composex.common import LOG
from ecs_composex.common.files import FileArtifact


class ComposeXStack(Stack, object):
    """
    Class to define a CFN Stack as a composition of its template object, parameters, tags etc.
    """

    template_file = None
    cfn_params_file = None
    cfn_config_file = None

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

    def render(self):
        """
        Function to use when the template is finalized and can be uploaded to S3.
        """
        LOG.debug(f"Rendering {self.title}")
        self.template_file.define_body()
        self.template_file.upload()
        self.template_file.write()
        self.template_file.validate()
        LOG.debug(f"Rendered URL = {self.template_file.url}")
        self.TemplateURL = self.template_file.url

    def __init__(self, title, template, template_file=None, extension=None, **kwargs):
        """
        Class to keep track of the template object along with the stack object it represents.

        :param title: title of the resource in the root template
        :param template: the template object to keep track of
        :param template_file: if the template file already exists, import
        :param extension: specify a specific file extension if you so wish
        :param render: whether the template should be rendered immediately
        :param kwargs: kwargs from composex along with the kwargs for the stack
        """

        if extension is None and template_file is None:
            extension = ".yml"
        self.stack_template = template
        if template_file and isinstance(template_file, FileArtifact):
            self.template_file = template_file
        else:
            file_name = f"{title}{extension}"
            self.template_file = FileArtifact(file_name, self.stack_template, **kwargs)
        if self.template_file.url is None:
            self.template_file.url = self.template_file.file_path
        stack_kwargs = dict((x, kwargs[x]) for x in self.props.keys() if x in kwargs)
        stack_kwargs.update(
            dict((x, kwargs[x]) for x in self.attributes if x in kwargs)
        )
        super().__init__(title, **stack_kwargs)
        self.TemplateURL = self.template_file.url
        if not hasattr(self, "DependsOn"):
            self.DependsOn = []


class XModuleStack(ComposeXStack):
    """
    Class to deal specifically with x-modules root stacks
    """


def render_final_template(root_template):
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
            LOG.debug(resource.TemplateURL)
            render_final_template(resource.stack_template)
            resource.render()
        elif isinstance(resource, Stack):
            LOG.warn(resource_name)
            LOG.warn(resource)
