# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

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

from compose_x_common.compose_x_common import keyisset
from troposphere import Ref, Tags
from troposphere.ec2 import LaunchTemplate, TagSpecifications
from troposphere.events import Rule
from troposphere.msk import Cluster, Configuration
from troposphere.ssm import Parameter as SSMParameter

from ecs_composex import __version__ as version
from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import add_parameters


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
    rendered_tags = []
    if isinstance(tags, list):
        for tag in tags:
            rendered_tags.append(
                {tag["Key"]: Ref(define_tag_parameter_title(tag["Key"]))}
            )
    elif isinstance(tags, dict):
        for tag in tags:
            rendered_tags.append({tag: Ref(define_tag_parameter_title(tag))})
    if tags:
        return Tags(*rendered_tags)
    return None


def generate_tags_parameters(tags):
    """
    Function to generate a list of parameters used for the tags values

    :return: list of parameters and tags to add to objects
    :rtype: tuple
    """
    parameters = []
    for tag in tags:
        parameters.append(
            Parameter(
                define_tag_parameter_title(tag["Key"])
                if isinstance(tags, list)
                else define_tag_parameter_title(tag),
                group_label="Tagging",
                Type="String",
                MinLength=2,
                MaxLength=128,
                AllowedPattern=r"[\x20-\x7E]+",
                ConstraintDescription="Must be ASCII",
                Default=tag["Value"] if isinstance(tags, list) else tags[tag],
            )
        )
    return parameters


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


def merge_tags_lists(x_data, y_data):
    x_keys = [x["Key"] for x in x_data]
    result = [{a["Key"]: a["Value"]} for a in x_data]
    for count, tag in enumerate(y_data):
        if tag["Key"] not in x_keys:
            result.append({y_data[count]["Key"]: y_data[count]["Value"]})
    return result


def add_object_tags(obj, tags):
    """
    Function to add tags to the object if the object supports it

    :param obj: Troposphere object to add the tags to
    :param troposphere.Tags tags: list of tags as defined in Docker composeX file
    """
    excluded_types = (SSMParameter, Cluster, Configuration, Rule)
    if tags is None:
        return
    clean_tags = copy.deepcopy(tags)
    if isinstance(obj, LaunchTemplate):
        expand_launch_template_tags_specs(obj, clean_tags)
        return
    elif isinstance(obj, excluded_types):
        return
    if hasattr(obj, "props") and "Tags" not in obj.props:
        LOG.debug(f"Item {obj} does not support tags")
        return
    if hasattr(obj, "Tags") and isinstance(getattr(obj, "Tags"), Tags):
        LOG.debug(f"Adding the new tags {clean_tags} to {obj}")
        existing_tags = getattr(obj, "Tags").to_dict()
        new_tags = clean_tags.to_dict()
        result = merge_tags_lists(existing_tags, new_tags)
        result_tags = Tags(*result)
        LOG.debug(result_tags)
        setattr(obj, "Tags", result_tags)
    elif not hasattr(obj, "Tags"):
        LOG.debug(f"No existing tags. Adding tags to {obj}")
        setattr(obj, "Tags", clean_tags)


def default_tags():
    """
    Function to return default tags to set on resource
    :return: default compose-x tags
    :rtype: troposphere.Tags
    """
    return Tags(CreatedByComposeX=True, **{"compose-x:version": version})


def apply_tags_to_resources(settings, resource, params, xtags):
    """

    :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
    :param resource: The resource to add the tags to
    :param list params: Parameters to add to template if any
    :param troposphere.Tags xtags: List of Tags to add to the resources.
    :return:
    """
    if isinstance(resource, ComposeXStack) or issubclass(type(resource), ComposeXStack):
        LOG.debug(resource)
        LOG.debug(resource.title)
        add_all_tags(resource.stack_template, settings, params, xtags)
        if params:
            add_parameters(resource.stack_template, params)
        if (
            not resource
            or not hasattr(resource, "stack_template")
            or not resource.stack_template
        ):
            return
        for stack_resource in resource.stack_template.resources.values():
            add_object_tags(stack_resource, xtags)


def add_all_tags(root_template, settings, params=None, xtags=None):
    """
    Function to go through all stacks of a given template and update the template
    It will recursively render sub stacks defined.
    If there are no substacks, it will go over the resources of the template add the tags.

    :param troposphere.Template root_template: the root template to iterate over the resources.
    :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
    :param list params: Parameters to add to template if any
    :param troposphere.Tags xtags: List of Tags to add to the resources.
    """
    if not params or not xtags:
        if not keyisset("x-tags", settings.compose_content):
            xtags = default_tags()
            params = None
        else:
            tags = settings.compose_content["x-tags"]
            params = generate_tags_parameters(tags)
            xtags = define_extended_tags(tags)
            xtags += default_tags()

    resources = root_template.resources if root_template else []
    for resource_name in resources:
        resource = resources[resource_name]
        apply_tags_to_resources(settings, resource, params, xtags)
