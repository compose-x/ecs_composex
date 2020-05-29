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
From the docker ComposeX definition file, allows to add generic tags to all objects supporting AWS Tags from CFN

Obviously as per AWS CFN API, when you create a stack with Tags, these tags propagate to all resources that support
tagging via CFN. Which is great, but very little people use that. And given that the AWS Stack itself has no cost,
the FinOps people usually only are able to track the resources that generate actual billing.

By adding the tags to the resources wherever supported and have these as parameters, this enforces the presence of some
tags, even though their values might differ. Using parameters to set the values also allows to copy-paste templates
within the same organization and simply change the values at the time of creating the CFN Stack.

You might have IAM policies in place to try to force tagging. I find this doesn't use a lot of parameters unless you had
an insane number of tags.

When defining the tags in ComposeX as a list, the names of your tags can contain some special characters which
otherwise you could not, i.e., *vpc::usage::ecsapps*

"""

import copy

from troposphere import Tags, Parameter, Ref
from troposphere.cloudformation import Stack
from troposphere.ec2 import LaunchTemplate, TagSpecifications

from ecs_composex.common import keyisset, NONALPHANUM, LOG, add_parameters
from ecs_composex.common.stacks import XModuleStack, ComposeXStack


def define_tag_parameter_title(tag_name):
    """
    Returns the formatted name title for a given tag

    :param tag_name: name of the tag as defined in the ComposeX file
    :type tag_name: str
    :return: reformatted tag name to work on CFN
    :rtype: str
    """
    return f"{NONALPHANUM.sub('', tag_name).strip().title()}Tag"


def define_extended_tags(tags):
    """
    Function to generate the tags to be added to objects from x-tags

    :param tags: tags as defined in composex file
    :type tags: list or dict
    :return: Tags() or None
    :rtype: troposphere.Tags or None
    """
    tags_keys = ["name", "value"]
    rendered_tags = []
    if isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, dict):
                raise TypeError("Tags must be of type", dict)
            elif not set(tag.keys()) == set(tags_keys):
                raise KeyError("Keys for tags must be", "value", "name")
            rendered_tags.append(
                {tag["name"]: Ref(define_tag_parameter_title(tag["name"]))}
            )
    elif isinstance(tags, dict):
        for tag in tags:
            rendered_tags.append({tag: Ref(define_tag_parameter_title(tag))})
    if tags:
        return Tags(*rendered_tags)
    return None


def generate_tags_parameters(composex_content):
    """
    Function to generate a list of parameters used for the tags values

    :param composex_content: docker composeX file content
    :type composex_content: dict
    :return: list of parameters and tags to add to objects
    :rtype: tuple
    """
    if not keyisset("x-tags", composex_content):
        LOG.info("No x-tags found. Skipping")
        return []
    xtags = composex_content["x-tags"]
    object_tags = define_extended_tags(xtags)
    parameters = []
    for tag in xtags:
        parameters.append(
            Parameter(
                define_tag_parameter_title(tag["name"])
                if isinstance(xtags, list)
                else define_tag_parameter_title(tag),
                Type="String",
                MinLength=2,
                MaxLength=128,
                AllowedPattern=r"[\x20-\x7E]+",
                ConstraintDescription="Must be ASCII",
                Default=tag["value"] if isinstance(xtags, list) else xtags[tag],
            )
        )
    return parameters, object_tags


def expand_launch_template_tags_specs(lt, tags):
    """
    Function to expand the LaunchTemplate TagSpecifications with defined x-tags.

    :param lt: the LaunchTemplate object
    :type: troposphere.ec2.LaunchTemplate
    :param tags: the Tags as built from x-tags
    :type tags: troposphere.Tags
    """
    LOG.debug("Setting tags to LaunchTemplate")
    try:
        launch_data = getattr(lt, "LaunchTemplateData")
        if hasattr(launch_data, "TagSpecifications"):
            tags_specs = getattr(launch_data, "TagSpecifications")
            if isinstance(tags_specs, list) and tags_specs:
                for tag_spec in tags_specs:
                    if not isinstance(tag_spec, TagSpecifications):
                        continue
                    original_tags = getattr(tag_spec, "Tags")
                    new_tags = original_tags + tags
                    setattr(tag_spec, "Tags", new_tags)
                setattr(launch_data, "TagSpecifications", tags_specs)
    except AttributeError:
        LOG.error("Failed to get the launch template data")
    except Exception as error:
        LOG.error(error)


def add_object_tags(obj, tags):
    """
    Function to add tags to the object if the object supports it

    :param obj: Troposphere object to add the tags to
    :param tags: list of tags as defined in Docker composeX file
    :type tags: dict or list
    """
    if tags is None:
        return
    clean_tags = copy.deepcopy(tags)
    if isinstance(obj, LaunchTemplate):
        expand_launch_template_tags_specs(obj, clean_tags)
    if hasattr(obj, "props") and "Tags" not in obj.props:
        return
    if hasattr(obj, "Tags") and isinstance(getattr(obj, "Tags"), Tags):
        LOG.debug(f"Adding the new tags {clean_tags} to {obj}")
        existing_tags = getattr(obj, "Tags")
        new_tags = existing_tags + clean_tags
        setattr(obj, "Tags", new_tags)
    elif not hasattr(obj, "Tags"):
        LOG.debug(f"Adding tags to {obj}")
        setattr(obj, "Tags", tags)


def add_all_tags(root_template, params_and_tags):
    """
    Function to go through all stacks of a given template and update the template
    It will recursively render sub stacks defined.
    If there are no substacks, it will go over the resources of the template add the tags.

    :param root_template: the root template to iterate over the resources.
    :type root_template: troposphere.Template
    :param params_and_tags: parameters and tags to add to the stack resources
    :type params_and_tags: ()
    """
    if not params_and_tags:
        return None
    resources = root_template.resources if root_template else []
    for resource_name in resources:
        resource = resources[resource_name]
        if isinstance(resource, (XModuleStack, ComposeXStack)):
            LOG.debug(resource)
            LOG.debug(resource.TemplateURL)
            add_all_tags(resource.stack_template, params_and_tags)
            add_parameters(resource.stack_template, params_and_tags[0])
            if (
                not resource
                or not hasattr(resource, "stack_template")
                or not resource.stack_template
            ):
                return
            for stack_resname in resource.stack_template.resources:
                add_object_tags(
                    resource.stack_template.resources[stack_resname], params_and_tags[1]
                )
        elif isinstance(resource, Stack):
            LOG.warn(resource_name)
            LOG.warn(resource)
